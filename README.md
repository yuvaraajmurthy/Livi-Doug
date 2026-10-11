# Compass backend

The layer between the Wellness Inventory and the help Rutgers already has: scores in → one next step that fits the
student's week (fit first, distance second) → plan, invite, reminder → "did it help?" → Arc credit, challenge,
retake nudge. Plus Staff Pulse aggregates. Rutgers Health Hack 2026, "Wellness, Reimagined".

- **Live API:** https://d2fap8zqnl1gn5.cloudfront.net (docs at `/docs`, contract at `contract/openapi.json`)
- **Design:** `docs/superpowers/specs/2026-10-10-compass-backend-design.md` · **Decisions:** `docs/DECISIONS.md`
- **Architecture + pitch numbers:** `docs/ARCHITECTURE.md` · **Runbook:** `docs/RUNBOOK.md`
- **Crisis lines call-down sheet:** `docs/crisis_lines_verification.md` (a human must verify before the demo)

All student data is synthetic and labelled. No names, emails, NetIDs or phone numbers of students anywhere.

## Run locally

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt     # (bin/ on macOS/Linux)
cp .env.example .env            # set DATABASE_URL (Postgres 16+ with pgvector; Neon or local both work)
python -m app.cli migrate       # schema (handoff schema_v2 + Compass additions + staff suppression functions)
python -m app.cli seed          # synthetic semester, personas, real KB, research items, pinned demo events
uvicorn app.main:app --port 8000
```
No database? `MODE=fixtures uvicorn app.main:app` serves realistic fixtures for every endpoint.
For AI calls locally, export AWS credentials for an account with Bedrock access (us-west-2).

## Demo controls

| Action | Call |
|---|---|
| Start as a persona | `POST /demo/session {"persona": "andre"}` (andre, priya, taylor, sofia, jordan, staff) |
| Set the simulated clock | `POST /demo/clock {"now": "2026-10-19T09:00:00-04:00"}` |
| Fire the next reminder / follow-up | `POST /demo/skip-ahead {"to": "next_due"}` (or `"+2d"`, or an ISO time) |
| Reset to the exact start state | `POST /demo/reset` (also re-warms AI wording in the background) |
| Stage switch: no model calls | `POST /demo/force-templates {"on": true}` |

## Test

```bash
python -m pytest                                  # unit, contract, safety (107 phrases), resilience
python -m scripts.smoke http://localhost:8000 --reset            # acceptance scenarios end to end
python -m scripts.smoke https://d2fap8zqnl1gn5.cloudfront.net --reset
```

## Ingest and data

```bash
python -m app.cli ingest            # Wellness Calendar + Scarlet Sync + geocoding + AI tagging (hourly on AWS)
python -m ingest.run --snapshot     # same, and refresh the committed offline snapshots/tags for seeding
python -m scripts.import_scores export.csv --mapping config/import_mapping.yaml   # a future ScarletWell export
```

## Deploy (AWS, us-west-2)

Needs AWS credentials in the environment and the CDK CLI (`npm i -g aws-cdk`). No local Docker needed (CodeBuild builds the image).
```bash
python -m scripts.create_guardrail                 # once: Bedrock guardrail -> SSM /compass/guardrail_id
python -m scripts.deploy --mode live --init-db     # base (ECR, CodeBuild, RDS) + image + app (ECS, ALB, CloudFront, Scheduler)
python -m scripts.deploy --skip-base               # code-only redeploy
python -m scripts.deploy --task "reset --full"     # any app.cli command as a one-off ECS task
```
Teardown: `cdk destroy CompassApp CompassBase` from `infra/` (every resource is tagged `project=compass`).
