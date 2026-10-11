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

Local-only demo: Postgres 17 + pgvector (Homebrew), a `.venv` (Python 3.14), and the Vite web app.

```bash
brew install postgresql@17 pgvector && brew services start postgresql@17       # then create the compass DB (and a test DB)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt              # (Scripts/ on Windows)
# .env (repo root): DATABASE_URL=postgresql://…/compass   TEST_DATABASE_URL=postgresql://…/compass_test
.venv/bin/python -m app.cli init   # migrate + seed + embeddings. Plain `seed` does not create embeddings, and re-running it drops them (`/demo/reset` keeps them)
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Web (separate terminal; `web/.env.local` holds `VITE_API_BASE=http://127.0.0.1:8000`):
```bash
npm --prefix web install
npm --prefix web run dev -- --port 5173 --strictPort    # then open http://127.0.0.1:5173
```
myRutgers mock: `integration/Index.html` is a myRutgers page whose **Doug** tab embeds the running app signed in as Jordan
(`http://127.0.0.1:5173/as/jordan`; override with `?app=<url>`). Serve it with `python3 -m http.server 5500` from
`integration/` and open http://127.0.0.1:5500/Index.html.

No database? `MODE=fixtures uvicorn app.main:app` serves realistic fixtures for every endpoint.
For AI calls locally, export AWS credentials for an account with Bedrock access in **us-east-1** (the chat/voice assistant)
and **us-west-2** (event wording, tagging, embeddings).

## AI assistant (chat + voice)

Chat and voice follow the team's tested voice bot (`app/chat/assist_aws.py`). Everything below runs in **us-east-1**
(`assistant_region` in `config/settings.py`) on the default boto3 credential chain.

- **Models:** chat is Claude Haiku 4.5 via Strands; voice is Amazon Nova 2.5 Sonic (`amazon.nova-2-5-sonic`) via a Strands BidiAgent.
- **Guardrail:** Bedrock guardrail `7a6u58w100yu` (version DRAFT) is fetched with `get_guardrail`, and its topics and blocked
  message are written into the system prompt ("ACTIVE BEDROCK GUARDRAIL RULES"), cached 10 minutes. Settings: `BEDROCK_GUARDRAIL_ID`, `BEDROCK_GUARDRAIL_VERSION`.
- **Knowledge base:** tool `search_knowledge_base` queries Bedrock Knowledge Base `DQTTJ5HDWT` (official Rutgers info: library
  spaces, room availability, campus info). Setting: `BEDROCK_KNOWLEDGE_BASE_ID`. Events still come from the pgvector `search_events` tool.
- **Email:** tool `send_email_notification(subject, message)` invokes the Lambda `SEND_TEXT_LAMBDA_ARN`
  (`arn:aws:lambda:us-east-1:204762614174:function:sendText`), which emails the configured recipient. Tests never call it (an autouse guard in `tests/conftest.py`).
- **Scheduling:** `set_reminder` in chat or voice creates the same plan, reminder and follow-up as the event card's "Remind me".
- **Other model calls** (event wording, tagging, embeddings) stay in `AWS_REGION` (us-west-2). The older `compass-guardrail`
  (us-west-2, `GUARDRAIL_ID`) is used only by `converse()` in `app/llm/bedrock.py`, and only if set; it is not set locally.

## Demo controls

| Action | Call |
|---|---|
| Start as a persona | `POST /demo/session {"persona": "andre"}` (andre, priya, taylor, sofia, jordan, staff) |
| Sign in from a URL (web) | `/as/:persona`, e.g. `/as/jordan`: signs straight in as that persona, reusing the tab's session (used by the myRutgers embed) |
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
The ECS task role also needs `bedrock:Retrieve` (knowledge base) and `lambda:InvokeFunction` on the sendText ARN for the assistant; both are already in `infra/compass_stack.py`.
Teardown: `cdk destroy CompassApp CompassBase` from `infra/` (every resource is tagged `project=compass`).
