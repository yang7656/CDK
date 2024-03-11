import os.path;

from aws_cdk.aws_s3_assets import Asset as S3asset

from aws_cdk import (
    # Duration,
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_rds as rds
)

from constructs import Construct

dirname = os.path.dirname(__file__)

class CdkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here
        
        # Create a VPC. CDK by default creates and attaches internet gateway for VPC
        # One public and one private subnets in one availability zone
        # One public and one private subnets in another availability zone
        cdk_assignment_vpc = ec2.Vpc(self, "cdk_assignment_vpc", 
                                ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
                                max_azs=2,
                                subnet_configuration=[
                                    ec2.SubnetConfiguration(name="PublicSubnet01", subnet_type=ec2.SubnetType.PUBLIC),
                                    ec2.SubnetConfiguration(name="PrivateSubnet01", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
                                ])
                                
        WebServerSecurityGroup = ec2.SecurityGroup(self, "WebServerSecurityGroup",
                                 vpc=cdk_assignment_vpc,
                                 description="Security Group")
        WebServerSecurityGroup.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "Allow HTTP")

        # Instance Role and SSM Managed Policy
        InstanceRole = iam.Role(self, "InstanceSSM", assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"))
        InstanceRole.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"))
        
        # Script in S3 as Asset
        webinitscriptasset = S3asset(self, "Asset", path=os.path.join(dirname, "configure.sh"))
        
        # Launch one web server in each public subnets
        for i, subnet in enumerate(cdk_assignment_vpc.public_subnets):
            instance = ec2.Instance(self,
                        f"cdk_assignment_instance_{i}",
                        vpc=cdk_assignment_vpc,
                        instance_type=ec2.InstanceType("t2.micro"),
                        machine_image=ec2.AmazonLinuxImage(generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2),
                        role=InstanceRole,
                        security_group=WebServerSecurityGroup,
                        vpc_subnets=ec2.SubnetSelection(subnets=[subnet]))
            
            asset_path = instance.user_data.add_s3_download_command(bucket=webinitscriptasset.bucket, bucket_key=webinitscriptasset.s3_object_key)
        
            # userdata execution
            instance.user_data.add_execute_file_command(file_path=asset_path)
            webinitscriptasset.grant_read(instance.role)
            
            # Allow inbound HTTP traffic in security groups
            # To open port 80 for HTTP traffic
            instance.connections.allow_from_any_ipv4(ec2.Port.tcp(80))
        
        
        # RDS DB with private subnet group
        RDSSubnetGroup = rds.SubnetGroup(self, "RDSSubnetGroup", description="RDS", vpc=cdk_assignment_vpc, vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS))
        
        # RDS instance with MySQL engine
        RDSInstance = rds.DatabaseInstance(self, "RDSInstance",
                        engine=rds.DatabaseInstanceEngine.mysql(version=rds.MysqlEngineVersion.VER_8_0),
                        subnet_group=RDSSubnetGroup,
                        vpc=cdk_assignment_vpc,
                        vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS))
                        
        # opens port 3306 to only web servers security group
        RDSInstance.connections.allow_from(WebServerSecurityGroup, ec2.Port.tcp(3306), "Allow access from Web Servers")