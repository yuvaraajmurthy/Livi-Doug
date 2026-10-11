import os
from pathlib import Path

import aws_cdk as cdk

from compass_stack import AppStack, BaseStack

app = cdk.App()
env = cdk.Environment(account=os.environ.get("CDK_DEFAULT_ACCOUNT", "204762614174"), region="us-west-2")
root = str(Path(__file__).resolve().parent.parent)

base = BaseStack(app, "CompassBase", repo_root=root, env=env)
AppStack(
    app, "CompassApp", base=base, env=env,
    image_tag=app.node.try_get_context("image_tag") or "latest",
    mode=app.node.try_get_context("mode") or "fixtures",
    origin_secret=app.node.try_get_context("origin_secret") or "dev-origin-secret",
)
cdk.Tags.of(app).add("project", "compass")
app.synth()
