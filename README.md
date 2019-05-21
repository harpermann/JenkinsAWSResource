Jenkins AWS Resources for App Developers

Introduction

Developers often need AWS resources created to support applications they write which are only relevant to the particular application.  We wanted allow developers to request simple AWS resources from a basic YAML configuration file contained in their application repository that could be generically picked up in the Jenkins builds.  So, if they need an S3 Bucket, they can define a name and a location string in aws.yml to get a basic bucket they can use for whatever is needed independent of Infrastructure code.
Design review

AWS resources can be created from configuration files with CloudFormation Templates (CFT) or Terraform but these are comprehensive tools which require proper context target resources.  We wanted to simplify what a developer would need to know so they could simply request something like a bucket with only a name and region without creating a full CFT Template file.   By creating the resources separate from infrastructure code, changes to infrastructure will not affect developer resources, nor would developer resources complicate infrastructure code.

We chose to write a boto3 python script to run from Jenkins builds to look for and read a simple configuration YAML file in the develops application repository (git) and create the resources from basic default parameters contained in the script, if the AWS resources don’t already exist.  

Requirements for the script:

1.	Read a configuration file and parse requested resources.
2.	The initial set of Resources are S3, ECR and RDS (Postgres).
3.	For each resource in YAML, create the resource with default parameters.
4.	For RDS, create the dB with a master user ID based on the name (nameMaster), generate a random password and put both credentials in AWS Secrets Manager.
5.	The operator or user can look up the password in Secrets Manager.
6.	RDS configuration is coded in the boto3 call in the script.
7.	RDS Security Group must be pre-created named 
8.	For ECR, create a simple ECR with the access policy coded in a variable in the script.
9.	For S3 create a bucket with the requested name with a policy coded in a variable in the script.
10.	Provide a -c / --config option to accept the YAML configuration file name (aws.yml)
11.	Add the script to the Jenkins build to find the YAML configuration file in the App repo.
12.	Run the script silently with correct exit codes so it functions properly called from Jenkins scripts.
13.	Provide a -v option to output relevant debug such as Policy and error codes.
14.	The script should be idempotent and not do anything if the resource already exists.


TL:DR (quick setup)
1.	Install aws_resources.py somewhere Jenkins can run it.
2.	Create a Security Group called “dev-rds-instance-postgres” which will be used in RDS creation. It can be named whatever, can be changed in the script or could be passed in as an arg.

 
3.	Create a yaml configuration file in the application repository (ie; “aws.yml”).  There is an example here: https://github.com/hmann-rms/work_in_progress/blob/master/aws.yml
  		harpers-bucket0:
            type: bucket
            locations: us-west-2
        harpersPG1:
            type: rds-postgres
4.	Add the python script to a CI/CD build in Jenkins with the path to the file in Jenkins workspace:
./aws_resources.py --config ./aws.yml

5.	Run the build.  Can also test from CLI: 
[hmann@jenkins]$ ./aws_resources.py --config ./aws.yml
RDS Postgres Instance: harpersPG1 created
Bucket: harpers-bucket0 created
6.	Check the defined resource(s) were properly created.
7.	Edit the script to change default parameters.
