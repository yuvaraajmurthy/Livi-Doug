"""Compass on AWS.

BaseStack: ECR repo, CodeBuild image builder (no local Docker needed), RDS PostgreSQL 16, secrets.
AppStack:  ECS Fargate service behind an ALB, CloudFront for HTTPS, hourly ingestion via EventBridge Scheduler.
"""
import json

from aws_cdk import (
    CfnOutput, Duration, RemovalPolicy, Stack,
    aws_cloudfront as cf,
    aws_cloudfront_origins as origins,
    aws_codebuild as codebuild,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_elasticloadbalancingv2 as elbv2,
    aws_iam as iam,
    aws_logs as logs,
    aws_rds as rds,
    aws_s3_assets as s3_assets,
    aws_scheduler as scheduler,
    aws_secretsmanager as sm,
)
from constructs import Construct

CLOUDFRONT_PREFIX_LIST = "pl-82a045eb"  # com.amazonaws.global.cloudfront.origin-facing (us-west-2)
SEND_TEXT_LAMBDA_ARN = "arn:aws:lambda:us-east-1:204762614174:function:sendText"  # = settings.send_text_lambda_arn


class BaseStack(Stack):
    def __init__(self, scope: Construct, cid: str, *, repo_root: str, **kw):
        super().__init__(scope, cid, **kw)
        self.vpc = ec2.Vpc.from_lookup(self, "Vpc", is_default=True)

        self.db_sg = ec2.SecurityGroup(self, "DbSg", vpc=self.vpc, description="Compass RDS", allow_all_outbound=False)

        self.db = rds.DatabaseInstance(
            self, "Db",
            engine=rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.of("16.10", "16")),
            instance_type=ec2.InstanceType("t4g.small"),
            vpc=self.vpc, vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            publicly_accessible=False, security_groups=[self.db_sg],
            credentials=rds.Credentials.from_generated_secret("compass_app", secret_name="compass/db"),
            database_name="compass", allocated_storage=20, storage_type=rds.StorageType.GP3,
            storage_encrypted=True, multi_az=False, backup_retention=Duration.days(1),
            deletion_protection=False, removal_policy=RemovalPolicy.DESTROY,
            cloudwatch_logs_exports=[],
        )

        self.app_secret = sm.Secret(
            self, "AppSecret", secret_name="compass/app",
            description="VAPID keys and demo signing key (filled by scripts/deploy.py)",
            secret_object_value={},
        )

        self.repo = ecr.Repository(self, "Repo", repository_name="compass-api", removal_policy=RemovalPolicy.DESTROY, empty_on_delete=True)

        source = s3_assets.Asset(self, "Source", path=repo_root, exclude=[
            ".venv", ".venv/**", ".git", ".git/**", "**/__pycache__/**", "infra/cdk.out", "infra/cdk.out/**", "cdk.out",
            "tests", "tests/**", "docs", "docs/**", ".env", "handoff/data/*.py", "node_modules",
        ])
        self.builder = codebuild.Project(
            self, "Builder", project_name="compass-image-builder",
            source=codebuild.Source.s3(bucket=source.bucket, path=source.s3_object_key),
            environment=codebuild.BuildEnvironment(build_image=codebuild.LinuxBuildImage.STANDARD_7_0, privileged=True,
                                                   compute_type=codebuild.ComputeType.SMALL),
            environment_variables={"REPO_URI": codebuild.BuildEnvironmentVariable(value=self.repo.repository_uri),
                                   "IMAGE_TAG": codebuild.BuildEnvironmentVariable(value="latest")},
            build_spec=codebuild.BuildSpec.from_source_filename("buildspec.yml"),
            timeout=Duration.minutes(20),
        )
        self.repo.grant_pull_push(self.builder)

        CfnOutput(self, "RepoUri", value=self.repo.repository_uri)
        CfnOutput(self, "BuilderName", value=self.builder.project_name)
        CfnOutput(self, "DbEndpoint", value=self.db.db_instance_endpoint_address)
        CfnOutput(self, "SourceKey", value=source.s3_object_key)


class AppStack(Stack):
    def __init__(self, scope: Construct, cid: str, *, base: BaseStack, image_tag: str, mode: str, origin_secret: str,
                 guardrail: str = "", **kw):
        super().__init__(scope, cid, **kw)
        vpc = base.vpc
        cluster = ecs.Cluster(self, "Cluster", vpc=vpc, cluster_name="compass")
        app_sg = ec2.SecurityGroup(self, "AppSg", vpc=vpc, description="Compass ECS tasks", allow_all_outbound=True)
        ec2.CfnSecurityGroupIngress(self, "DbFromApp", group_id=base.db_sg.security_group_id, ip_protocol="tcp",
                                    from_port=5432, to_port=5432, source_security_group_id=app_sg.security_group_id,
                                    description="ECS tasks only")

        log_group = logs.LogGroup(self, "Logs", log_group_name="/compass/api", retention=logs.RetentionDays.ONE_WEEK,
                                  removal_policy=RemovalPolicy.DESTROY)

        task_role = iam.Role(self, "TaskRole", assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"))
        task_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream", "bedrock:Converse",
                     "bedrock:ConverseStream", "bedrock:ApplyGuardrail", "bedrock:GetGuardrail",
                     "bedrock:InvokeModelWithBidirectionalStream", "bedrock:Retrieve"],
            resources=["*"]))
        # chat/voice email tool (voice_bot.py port): the sendText Lambda in us-east-1, nothing else
        task_role.add_to_policy(iam.PolicyStatement(actions=["lambda:InvokeFunction"], resources=[SEND_TEXT_LAMBDA_ARN]))
        task_role.add_to_policy(iam.PolicyStatement(
            actions=["geo:SearchPlaceIndexForText", "geo-places:Geocode", "geo-places:SearchText"], resources=["*"]))

        image = ecs.ContainerImage.from_ecr_repository(base.repo, tag=image_tag)
        db_secret = base.db.secret
        secrets = {
            "DB_HOST": ecs.Secret.from_secrets_manager(db_secret, "host"),
            "DB_USER": ecs.Secret.from_secrets_manager(db_secret, "username"),
            "DB_PASSWORD": ecs.Secret.from_secrets_manager(db_secret, "password"),
            "VAPID_PUBLIC_KEY": ecs.Secret.from_secrets_manager(base.app_secret, "vapid_public_key"),
            "VAPID_PRIVATE_KEY": ecs.Secret.from_secrets_manager(base.app_secret, "vapid_private_key"),
            "DEMO_SIGNING_KEY": ecs.Secret.from_secrets_manager(base.app_secret, "demo_signing_key"),
        }
        env = {"MODE": mode, "ENV": "prod", "AWS_REGION": self.region, "DB_NAME": "compass",
               "CORS_ORIGINS": "*", "IMAGE_TAG": image_tag}
        if guardrail:
            gid, _, gver = guardrail.partition(":")
            env.update({"GUARDRAIL_ID": gid, "GUARDRAIL_VERSION": gver or "DRAFT"})

        def task_def(name: str, cpu: int, mem: int) -> ecs.FargateTaskDefinition:
            td = ecs.FargateTaskDefinition(self, name, cpu=cpu, memory_limit_mib=mem, task_role=task_role,
                                           runtime_platform=ecs.RuntimePlatform(cpu_architecture=ecs.CpuArchitecture.X86_64,
                                                                                operating_system_family=ecs.OperatingSystemFamily.LINUX))
            td.add_container("api", image=image, environment=env, secrets=secrets,
                             logging=ecs.LogDriver.aws_logs(stream_prefix=name.lower(), log_group=log_group),
                             port_mappings=[ecs.PortMapping(container_port=8000)])
            return td

        api_td = task_def("ApiTask", 1024, 2048)
        self.job_td = task_def("JobTask", 512, 1024)

        service = ecs.FargateService(
            self, "Service", cluster=cluster, task_definition=api_td, desired_count=1, assign_public_ip=True,
            security_groups=[app_sg], vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            min_healthy_percent=100, max_healthy_percent=200, health_check_grace_period=Duration.seconds(60),
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
        )

        alb_sg = ec2.SecurityGroup(self, "AlbSg", vpc=vpc, description="Compass ALB: CloudFront only", allow_all_outbound=True)
        alb_sg.add_ingress_rule(ec2.Peer.prefix_list(CLOUDFRONT_PREFIX_LIST), ec2.Port.tcp(80), "CloudFront origin-facing")
        app_sg.add_ingress_rule(alb_sg, ec2.Port.tcp(8000), "ALB to tasks")
        alb = elbv2.ApplicationLoadBalancer(self, "Alb", vpc=vpc, internet_facing=True, security_group=alb_sg,
                                            idle_timeout=Duration.seconds(120))
        listener = alb.add_listener("Http", port=80, open=False,
                                    default_action=elbv2.ListenerAction.fixed_response(403, content_type="text/plain", message_body="forbidden"))
        tg = elbv2.ApplicationTargetGroup(self, "Tg", vpc=vpc, port=8000, protocol=elbv2.ApplicationProtocol.HTTP,
                                          targets=[service], deregistration_delay=Duration.seconds(10),
                                          health_check=elbv2.HealthCheck(path="/health", healthy_http_codes="200", interval=Duration.seconds(15)))
        listener.add_action("FromCloudFront", priority=10,
                            conditions=[elbv2.ListenerCondition.http_header("X-Origin-Verify", [origin_secret])],
                            action=elbv2.ListenerAction.forward([tg]))

        dist = cf.Distribution(
            self, "Cdn", comment="Compass API",
            default_behavior=cf.BehaviorOptions(
                origin=origins.HttpOrigin(alb.load_balancer_dns_name, protocol_policy=cf.OriginProtocolPolicy.HTTP_ONLY,
                                          custom_headers={"X-Origin-Verify": origin_secret}, read_timeout=Duration.seconds(60)),
                viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cf.AllowedMethods.ALLOW_ALL,
                cache_policy=cf.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cf.OriginRequestPolicy.ALL_VIEWER,
            ),
            price_class=cf.PriceClass.PRICE_CLASS_100,
        )

        # Hourly ingestion: EventBridge Scheduler -> ECS RunTask (python -m app.cli ingest)
        sched_role = iam.Role(self, "SchedulerRole", assumed_by=iam.ServicePrincipal("scheduler.amazonaws.com"))
        sched_role.add_to_policy(iam.PolicyStatement(actions=["ecs:RunTask"], resources=[self.job_td.task_definition_arn]))
        sched_role.add_to_policy(iam.PolicyStatement(actions=["iam:PassRole"], resources=[
            self.job_td.task_role.role_arn, self.job_td.obtain_execution_role().role_arn]))
        scheduler.CfnSchedule(
            self, "IngestHourly", name="compass-ingest-hourly", schedule_expression="rate(1 hour)",
            flexible_time_window=scheduler.CfnSchedule.FlexibleTimeWindowProperty(mode="OFF"),
            state="ENABLED" if mode == "live" else "DISABLED",
            target=scheduler.CfnSchedule.TargetProperty(
                arn=cluster.cluster_arn, role_arn=sched_role.role_arn,
                input=json.dumps({"containerOverrides": [{"name": "api", "command": ["python", "-m", "app.cli", "ingest"]}]}),
                ecs_parameters=scheduler.CfnSchedule.EcsParametersProperty(
                    task_definition_arn=self.job_td.task_definition_arn, launch_type="FARGATE", task_count=1,
                    network_configuration=scheduler.CfnSchedule.NetworkConfigurationProperty(
                        awsvpc_configuration=scheduler.CfnSchedule.AwsVpcConfigurationProperty(
                            subnets=[s.subnet_id for s in vpc.public_subnets], security_groups=[app_sg.security_group_id],
                            assign_public_ip="ENABLED"))),
            ),
        )

        CfnOutput(self, "ApiUrl", value=f"https://{dist.distribution_domain_name}")
        CfnOutput(self, "ClusterName", value=cluster.cluster_name)
        CfnOutput(self, "JobTaskDef", value=self.job_td.task_definition_arn)
        CfnOutput(self, "SubnetIds", value=",".join(s.subnet_id for s in vpc.public_subnets))
        CfnOutput(self, "AppSgId", value=app_sg.security_group_id)
        CfnOutput(self, "ServiceName", value=service.service_name)
