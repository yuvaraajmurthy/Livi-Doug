"""One-command deploy. Needs AWS credentials in the environment and the CDK CLI (npm i -g aws-cdk).

  python -m scripts.deploy                 # build image + deploy app (mode from --mode, default live)
  python -m scripts.deploy --mode fixtures
  python -m scripts.deploy --skip-base     # app code change only
  python -m scripts.deploy --init-db       # also run migrate + seed as a one-off ECS task
  python -m scripts.deploy --task reset    # run any app.cli command as a one-off task
  python -m scripts.deploy --web           # build web/ and deploy it (S3 + CloudFront) only
"""
import argparse
import base64
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent.parent
INFRA = ROOT / "infra"
REGION = "us-west-2"
sm = boto3.client("secretsmanager", region_name=REGION)


def sh(cmd: list[str], cwd: Path = INFRA) -> None:
    print("$", " ".join("origin_secret=***" if c.startswith("origin_secret=") else c for c in cmd), flush=True)
    env = {**os.environ, "CDK_DEFAULT_ACCOUNT": boto3.client("sts").get_caller_identity()["Account"]}
    venv_scripts = str(Path(sys.executable).parent)
    env["PATH"] = venv_scripts + os.pathsep + env["PATH"]
    subprocess.run(cmd, cwd=cwd, env=env, check=True, shell=(os.name == "nt"))


def ensure_app_secret() -> dict:
    cur = json.loads(sm.get_secret_value(SecretId="compass/app")["SecretString"] or "{}")
    changed = False
    if not cur.get("vapid_private_key"):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        key = ec.generate_private_key(ec.SECP256R1())
        priv = key.private_numbers().private_value.to_bytes(32, "big")
        pub = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        b64 = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
        cur["vapid_private_key"], cur["vapid_public_key"] = b64(priv), b64(pub)
        changed = True
    for k in ("demo_signing_key", "origin_secret"):
        if not cur.get(k):
            cur[k] = secrets.token_urlsafe(32)
            changed = True
    if changed:
        sm.put_secret_value(SecretId="compass/app", SecretString=json.dumps(cur))
        print("app secret updated")
    return cur


def outputs(stack: str) -> dict:
    cf = boto3.client("cloudformation", region_name=REGION)
    return {o["OutputKey"]: o["OutputValue"] for o in cf.describe_stacks(StackName=stack)["Stacks"][0].get("Outputs", [])}


def build_image(tag: str) -> None:
    cb = boto3.client("codebuild", region_name=REGION)
    b = cb.start_build(projectName="compass-image-builder",
                       environmentVariablesOverride=[{"name": "IMAGE_TAG", "value": tag, "type": "PLAINTEXT"}])["build"]
    print("codebuild", b["id"], flush=True)
    while True:
        time.sleep(10)
        st = cb.batch_get_builds(ids=[b["id"]])["builds"][0]
        print("  ", st["currentPhase"], st["buildStatus"], flush=True)
        if st["buildStatus"] != "IN_PROGRESS":
            if st["buildStatus"] != "SUCCEEDED":
                sys.exit(f"image build failed: {st['buildStatus']}")
            return


def run_task(command: list[str]) -> None:
    o = outputs("CompassApp")
    ecs = boto3.client("ecs", region_name=REGION)
    r = ecs.run_task(cluster=o["ClusterName"], taskDefinition=o["JobTaskDef"], launchType="FARGATE",
                     networkConfiguration={"awsvpcConfiguration": {"subnets": o["SubnetIds"].split(","),
                                                                   "securityGroups": [o["AppSgId"]], "assignPublicIp": "ENABLED"}},
                     overrides={"containerOverrides": [{"name": "api", "command": command}]})
    arn = r["tasks"][0]["taskArn"]
    print("task", arn, flush=True)
    ecs.get_waiter("tasks_stopped").wait(cluster=o["ClusterName"], tasks=[arn], WaiterConfig={"Delay": 10, "MaxAttempts": 90})
    t = ecs.describe_tasks(cluster=o["ClusterName"], tasks=[arn])["tasks"][0]
    code = t["containers"][0].get("exitCode")
    print("task exit", code, t.get("stoppedReason"))
    if code != 0:
        sys.exit("one-off task failed; see CloudWatch /compass/api")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="live", choices=["live", "fixtures"])
    ap.add_argument("--skip-base", action="store_true")
    ap.add_argument("--skip-build", action="store_true")
    ap.add_argument("--tag")
    ap.add_argument("--init-db", action="store_true")
    ap.add_argument("--task")
    ap.add_argument("--web", action="store_true", help="build and deploy the web app only")
    a = ap.parse_args()

    if a.web:
        deploy_web()
        return
    if a.task:
        run_task(["python", "-m", "app.cli", *a.task.split()])
        return
    secret = ensure_app_secret()
    tag = a.tag or subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip() + f"-{int(time.time()) % 100000}"
    if not a.skip_base or not a.skip_build:
        # The image source is an S3 asset of the base stack, so a code change always refreshes the base stack first.
        sh(["cdk", "deploy", "CompassBase", "--require-approval", "never"])
    if not a.skip_build:
        build_image(tag)
    try:
        guardrail = boto3.client("ssm", region_name=REGION).get_parameter(Name="/compass/guardrail_id")["Parameter"]["Value"]
    except Exception:
        guardrail = ""
    sh(["cdk", "deploy", "CompassApp", "--require-approval", "never", "--exclusively",
        "-c", f"image_tag={tag}", "-c", f"mode={a.mode}", "-c", f"origin_secret={secret['origin_secret']}",
        "-c", f"guardrail={guardrail}"])
    if a.init_db:
        run_task(["python", "-m", "app.cli", "init"])
    print("API:", outputs("CompassApp").get("ApiUrl"))


def deploy_web() -> None:
    api = outputs("CompassApp").get("ApiUrl") or "https://d2fap8zqnl1gn5.cloudfront.net"
    web = ROOT / "web"
    env = {**os.environ, "VITE_API_BASE": api}
    print(f"$ npm run build (VITE_API_BASE={api})", flush=True)
    subprocess.run(["npm", "run", "build"], cwd=web, env=env, check=True, shell=(os.name == "nt"))
    sh(["cdk", "deploy", "CompassWeb", "--require-approval", "never", "--exclusively"])
    print("WEB:", outputs("CompassWeb").get("WebUrl"))


if __name__ == "__main__":
    main()
