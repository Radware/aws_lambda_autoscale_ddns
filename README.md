# AWS Lambda function to update Route 53 DNS entries when auto scaling group events occur
AWS Lambda function written in Python 2.7 which triggers Route 53 DNS updates when auto scaling event occurs.

Alteon can then use DNS queries to autodiscover instance changes in the auto scaling group

For a detailed explanation on how to deploy and use this Lambda script refer to the following [Video](https://www.youtube.com/watch?v=adV8-_hgL4g)

## Lambda Function Flow Description
* This Lambda function gets triggered by CloudWatch for every instance event in auto scaling group (Instance Launch/Instance Terminate)
* It first checks if the `alteon.internal.` Hosted Zone exists for same VPC from which the autosclaing group event was triggered. If the Hosted Zone exists it obtains its ID. If not, it creates it and obtains its ID.
* Next it creates a list of the private IP addresses of all active instances in the autoscaling group which triggered this event
* If the list contains at least one IP address  - it creates or updates (if already exists) an A type DNS record set named `<auto_scaling_group_name>.alteon.internal.` with the  IP addresses in the list
* If the list is empty - It means the auto scaling group was deleted or doesnt contain any active instance. it deletes (if exists) the record set named `<auto_scaling_group_name>.alteon.internal.`

(`.alteon.internal.`can be modified to some other name by replacing the value of the variable `domain` at the beginning of the lambda function

## Lambda Function Flow Diagram
![alt text](https://raw.githubusercontent.com/Radware/aws_lambda_autoscale_ddns/master/aws_autoscale_flow.png "Flow diagram")

## Files
* `aws_lambda_autoscale_ddns.py` - the actual Lambda function (written in Python 2.7)
* `cloudwatch_event.json` - JSON file that includes all the CloudWatch events that should trigger this Lambda function
* `execution_role.json` - JSON file that includes all the permissions required for the Lambda function to work properly

