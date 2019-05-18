#! /usr/bin/python
#
# Script to create AWS resources if they're not already created
#
# Author: Harper Mann
#

import getopt
import sys
import yaml
from pathlib2 import Path
import boto3, botocore
from botocore.exceptions import ClientError
import json

BLUE  = '\033[0;34m'
GREEN = '\033[0;32m'
RED   = '\033[0;31m'
NC    = '\033[0m'

# Policies
ECRPolicy = """\
{ "Version": "2012-10-17", "Statement": [
    {
      "Sid": "full",
      "Effect": "Allow",
      "Principal": {
        "AWS": [
          "arn:aws:iam::123456789012:user/devops",
          "arn:aws:iam::123456789012:root",
        ]
      },
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:BatchDeleteImage",
        "ecr:BatchGetImage",
        "ecr:CompleteLayerUpload",
        "ecr:DeleteRepository",
        "ecr:DeleteRepositoryPolicy",
        "ecr:DescribeRepositories",
        "ecr:GetDownloadUrlForLayer",
        "ecr:GetRepositoryPolicy",
        "ecr:InitiateLayerUpload",
        "ecr:ListImages",
        "ecr:PutImage",
        "ecr:SetRepositoryPolicy",
        "ecr:UploadLayerPart"
      ]
    }
  ]
} """

# authenticate AWS
def connect_aws():
    global s3_client, ecr_client, rds_client, scr_client
    s3_client  = boto3.client('s3')
    ecr_client = boto3.client('ecr')
    rds_client = boto3.client('rds')
    scr_client = boto3.client('secretsmanager')

# S3
def bucket(name, locations):
    if verbose:
        print "creating bucket " + name
        print "  locations " + locations

    try:
        s3_client.create_bucket(
            Bucket = name,
            CreateBucketConfiguration = {'LocationConstraint': locations}
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'BucketAlreadyOwnedByYou':
            if verbose:
                print(BLUE + "  Bucket " + name  + " already exists" + NC)
        else:
            print "Bucket: " + name
            print("%sUnexpected error: %s%s" % (RED, e, NC))
            print ""
            return False
        return True

    print GREEN + "Bucket: " + name + " created" + NC

# ECR
def ecr(name):
    if verbose:
        print "creating ECR " + name
        print "  ECR policy"
        print ECRPolicy

    try:
        response = ecr_client.create_repository(
            repositoryName = name
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'RepositoryAlreadyExistsException':
            if verbose:
                print(BLUE + "  ECR repository " + name  + " already exists" + NC)
        else:
            print "ECR Repository: " + name
            print("$sUnexpected error: %s%s" % (RED, e, NC))
            print ""
            return False
        return True

    registryId     = response['repository']['registryId']
    repositoryName = response['repository']['repositoryName']

    if verbose:
        print "  ECR repositoryName: " + repositoryName
        print "  ECR registryId: " + registryId

    # Set the ECR policy
    try:
        response = ecr_client.set_repository_policy(
            registryId     = registryId,
            repositoryName = repositoryName,
            policyText     = ECRPolicy,
            force          = False
        )
    except ClientError as e:
        print "ECR repository: " + name
        print("%sUnexpected error: %s%s" % (RED, e, NC))
        print ""
        return False

    print GREEN + "ECR Repository: " + name + " created" + NC

# RDS
def rds_pg(name):
    if verbose:
        print "creating RDS Postgres Instance " + name

    # Password in AWS Secrets Manager, ExcludeCharacters has RDS excludes
    try:
        response = scr_client.get_random_password(
            PasswordLength = 16,
            ExcludeCharacters = '/ " @'
        )
    except ClientError as e:
        print("%sUnexpected error: %s%s" % (RED, e, NC))
        return False

    random_password = response['RandomPassword']    
    
    user          = name + "Master"
    secret_string = json.dumps({"Name":user,"Password":random_password})

    try:
        response = scr_client.create_secret(
            Name         = name,
            SecretString = secret_string
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceExistsException':
            if verbose:
                print(BLUE + "  RDS Postgres Secret " + name  + " already exists" + NC)
        else:
            print "RDS postgres instance: " + name
            print("%sUnexpected error: %s%s" % (RED, e, NC))
            print ""
            return False
        return True

    # dB create
    try:
        response = rds_client.create_db_instance(
            DBName                      = name,
            DBInstanceIdentifier        = name,
            DBInstanceClass             = "db.m4.large",  
            DBSubnetGroupName           = "dev-rds-instance-postgres",
            VpcSecurityGroupIds         = [ 'sg-096b1f1e917a7ffde' ],
            BackupRetentionPeriod       = 1,
            Engine                      = 'postgres',
            MasterUserPassword          = random_password,
            MasterUsername              = user,
            AllocatedStorage            = 5,
            StorageEncrypted            = True
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'DBInstanceAlreadyExists':
            if verbose:
                print(BLUE + "  RDS Postgres DBInstance " + name  + " already exists" + NC)
        else:
            print "RDS postgres instance: " + name
            print("%sUnexpected error: %s%s" % (RED, e, NC))
            print ""
            return False
        return True

    print GREEN + "RDS Postgres Instance: " + name + " created" + NC

def usage():
    script = sys.argv[0]
    print "usage: " +  sys.argv[0] + " --config-file <config yml>"
    print GREEN + "    example: " +  sys.argv[0] + " --config-file aws.yml" + NC
    sys.exit(1)

# The mains
def main():
    global verbose

    try:
        opts, args = getopt.getopt(sys.argv[1:], "c:hv", ["config-file=", "help"])
    except getopt.GetoptError as err:
        # print help information and exit:
        print str(err)  # will print something like "option -a not recognized"
        usage()
    output = None
    verbose = False
    config_file = ""
    if not opts:
      usage()
      
    for o, a in opts:
        if o == "-v":
            verbose = True
        elif o in ("-h", "--help"):
            usage()
        elif o in ("-c", "--config-file"):
            config_file = a
        else:
            assert False, "unhandled option"

    # Read yaml into a dictionary
    document = open(config_file, 'r').read()
    config_list = yaml.load(document)
    if verbose:
        print yaml.dump(config_list)

    connect_aws()

    # Walk the dict and parse by type
    exit_code = 0
    if not config_list:
        print RED + "AWS Resources not found in " + config_file + NC
        sys.exit(1)

    for row in config_list:
        type                = config_list[row]["type"]
        locations           = config_list[row]["locations"]

        if type == "bucket":
           if bucket(row, locations) == False:
               exit_code = 1
        elif type == "ecr":
           if ecr(row) == False:
               exit_code = 1
        elif type =="rds-postgres":
           if rds_pg(row) == False:
               exit_code = 1
        else:
           print "Error " + type + " UNKNOWN"

    sys.exit(exit_code)

if __name__ == "__main__":
    main()

