import boto3
import sys
import time

ec2_client = boto3.client('ec2')
asg_client = boto3.client('autoscaling')
r53_client = boto3.client('route53')

domain = "alteon.internal."
ttl = 60

def lambda_handler(event, context):
    """
    - This lambda function gets triggered for every event in auto scaling group (Instance Launch/Instance Terminate)
    - It first checks if the 'alteon.internal.' Hosted Zone exists for same VPC from which the autosclaing group event was triggered
    - If Hosted Zone exists it obtains its ID
    - Else Hosted Zone doesn't exist it creates it and obtains its ID
    - Next it obtains a list of private IPs of all active instances in the autoscaling group which triggered this event
    - If the list contains at least one instance it creates or updates a record set named '<autoscaling_group_name>.alteon.internal.' with the private IPs of the instances as A records
    - Else the list is empty (which means the auto scaling group was deleted or doesnt contain any active instance) it deletes the record set named '<autoscaling_group_name>.alteon.internal.'
    """
    asg_name = event['detail']['AutoScalingGroupName']
    record_set_name = asg_name + "." + domain
    event_region = event['region']
    for subnet in ec2_client.describe_subnets(SubnetIds=[event['detail']['Details']['Subnet ID']])['Subnets']:
        event_vpc_id = subnet['VpcId']
    print "{} in autoscaling group {} under VPC ID {}".format(event['detail']['Description'], asg_name, event_vpc_id)
    # If Hosted Zone exists in Route53 obtain its ID.
    hosted_zone_id = get_hosted_zone_id(domain, event_vpc_id)
    if hosted_zone_id:
        print "HostedZone {} under VPC ID {} in region {} exists in with ID {}".format(domain, event_vpc_id, event_region, hosted_zone_id)
    # Else Hosted Zone doesn't exist in Route53 create it and obtain its ID.
    else:
        print "Hosted Zone {} Doesn't exists under VPC ID {} in region {}. going to create it".format(domain, event_vpc_id, event_region)
        hosted_zone_id = create_hosted_zone(domain, event_region, event_vpc_id)
        if hosted_zone_id:
            print "HostedZone {} under VPC ID {} in region {} was created successfully with ID {}".format(domain, event_vpc_id, event_region, hosted_zone_id)
        else:
            print "HostedZone {} under VPC ID {} in region {} was already created by other instance of the lambda function - aborting".format(domain, event_vpc_id, event_region)
            sys.exit()            
    # Obtain Private IPs of all active instances in the auto scaling group which triggered this event.
    servers = get_asg_private_ips(asg_name)
    # If there are Private IPs it means the autoscaling group exists and contains at least one active instances. Create/Update record set in Route53 Hosted Zone.
    if servers:
        update_hosted_zone_records(hosted_zone_id, record_set_name, ttl, servers)
        print "Record set {} was created/updated successfully with the following A records {}".format(record_set_name, servers)
    # If there are no Private IPs it means the autoscaling group was deleted or doesn't contain any active instances. Remove record set from Hosted Zone in Route53.
    else:
        print "Auto Scaling group {} does not exist or empty - going to remove relevent A records".format(asg_name)
        delete_hosted_zone_records(hosted_zone_id, record_set_name)


def get_hosted_zone_id(domain, event_vpc_id):
    for hosted_zone in r53_client.list_hosted_zones()['HostedZones']:
        if hosted_zone['Name'] == domain and hosted_zone['Config']['PrivateZone'] == True:
            for vpc in r53_client.get_hosted_zone(Id = hosted_zone['Id'])['VPCs']:
                if vpc['VPCId'] == event_vpc_id:
                    return hosted_zone['Id']
    else:
        return False


def create_hosted_zone(domain, event_region, event_vpc_id):
    try:    
        response = r53_client.create_hosted_zone(
            Name = domain,
            VPC = {
                'VPCRegion': str(event_region),
                'VPCId': event_vpc_id
            },
            CallerReference = str(time.time()),
            HostedZoneConfig = {
                'Comment': "Created by Radware lambda fucntion for VPC {} in region {}".format(event_vpc_id, event_region),
                'PrivateZone': True
            }
        )
        return response['HostedZone']['Id']
    except:
        return False


def get_asg_private_ips(asg_name):
    for asg in asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])['AutoScalingGroups']:
        instance_ids = []
        for instance in asg['Instances']:
            if instance['LifecycleState'] == 'InService':
                instance_ids.append(instance['InstanceId'])
        if instance_ids:
            servers = []
            for reservation in ec2_client.describe_instances(InstanceIds = instance_ids)['Reservations']:
                for instance in reservation['Instances']:
                    if instance['State']['Name'] == 'running':
                        servers.append({'Value': instance['PrivateIpAddress']})
            return servers


def update_hosted_zone_records(hosted_zone_id, record_set_name, ttl, servers):
    r53_client.change_resource_record_sets(
    HostedZoneId = hosted_zone_id,
    ChangeBatch = {
        'Changes': [
            {
            'Action': 'UPSERT',
            'ResourceRecordSet': {
                'Name': record_set_name,
                'Type': 'A',
                'TTL': ttl,
                'ResourceRecords': servers
            }
        }]
    })
    return


def delete_hosted_zone_records(hosted_zone_id, record_set_name):
    for record_set in r53_client.list_resource_record_sets(HostedZoneId = hosted_zone_id)['ResourceRecordSets']:
        if record_set['Name'] == record_set_name:
            try:
                r53_client.change_resource_record_sets(
                HostedZoneId = hosted_zone_id,
                ChangeBatch = {
                    'Changes': [
                        {
                        'Action': 'DELETE',
                        'ResourceRecordSet': record_set
                    }]
                })
                print "Record set {} removed successfully".format(record_set_name)
            except:
                print "Record set {} was already removed by other instance of the lambda function".format(record_set_name)
            break
    else:
        print "Record set {} was already removed by other instance of the lambda function".format(record_set_name)
