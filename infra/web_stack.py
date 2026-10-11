"""Static web app: private S3 bucket behind CloudFront (HTTPS), SPA fallback to index.html.

Hashed assets are cached for a year; index.html, the service worker and the manifest are always revalidated."""
from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_cloudfront as cf
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as deploy
from constructs import Construct

ALWAYS_FRESH = ["index.html", "sw.js", "manifest.webmanifest"]


class WebStack(Stack):
    def __init__(self, scope: Construct, cid: str, *, dist_dir: str, **kw) -> None:
        super().__init__(scope, cid, **kw)
        bucket = s3.Bucket(
            self, "Site", block_public_access=s3.BlockPublicAccess.BLOCK_ALL, enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY, auto_delete_objects=True,
        )
        dist = cf.Distribution(
            self, "Cdn",
            comment="Compass web app",
            default_behavior=cf.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(bucket),
                viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cf.CachePolicy.CACHING_OPTIMIZED,
                response_headers_policy=cf.ResponseHeadersPolicy.SECURITY_HEADERS,
                compress=True,
            ),
            default_root_object="index.html",
            error_responses=[
                cf.ErrorResponse(http_status=code, response_http_status=200, response_page_path="/index.html",
                                 ttl=Duration.seconds(0))
                for code in (403, 404)
            ],
        )
        assets = deploy.BucketDeployment(
            self, "Assets", sources=[deploy.Source.asset(dist_dir)], destination_bucket=bucket,
            exclude=ALWAYS_FRESH, prune=False,
            cache_control=[deploy.CacheControl.from_string("public, max-age=31536000, immutable")],
        )
        fresh = deploy.BucketDeployment(
            self, "Fresh", sources=[deploy.Source.asset(dist_dir)], destination_bucket=bucket,
            exclude=["*"], include=ALWAYS_FRESH, prune=False,
            cache_control=[deploy.CacheControl.from_string("no-cache")],
            distribution=dist, distribution_paths=["/*"],
        )
        fresh.node.add_dependency(assets)  # new index.html only after the assets it references exist
        CfnOutput(self, "WebUrl", value=f"https://{dist.distribution_domain_name}")
