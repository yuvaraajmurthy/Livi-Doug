# Demo-day runbook

API: `https://d2fap8zqnl1gn5.cloudfront.net` · Web: `https://dtgnmjb9o6f1k.cloudfront.net` · Stage: `/present` (notes window: N) · Health: `/health` (add `?deep=true` to probe Bedrock)

Running locally instead (current setup): API `.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000`, web `npm --prefix web run dev -- --port 5173 --strictPort` → http://127.0.0.1:5173 (see README "Run locally"). Chat and voice use Bedrock in us-east-1; event wording, tagging and embeddings use us-west-2, so credentials need both. If the embeddings are missing, run `python -m app.cli init` (plain `seed` does not create them and re-running it drops them; `/demo/reset` keeps them).

## 30 minutes before
1. `POST /demo/reset` → wait ~1 min for wording pre-warm, then `GET /health?deep=true` (db ok, bedrock ok).
2. `python -m scripts.smoke https://d2fap8zqnl1gn5.cloudfront.net --reset --quick` → must print `RESULT: ALL PASS`.
3. Crisis lines: confirm every row in `docs/crisis_lines_verification.md` is verified.
4. Chat: on the web, Chat tab, ask "anything social with free food this week?" → event buttons within ~5 s; tap one → card with map and Remind me.
5. Voice: on the actual demo laptop/phone, tap the mic in Chat, allow the microphone, ask the same question → spoken answer plus event chips. Needs HTTPS (or 127.0.0.1) and a mic permission grant; test the room's audio.
6. Reset once more right before going on stage.

## The Andre script (what the backend does)
| Step | Call | Expect |
|---|---|---|
| Open as Andre | `POST /demo/session {"persona":"andre"}` | clock Mon Oct 12, 9:00 |
| Wellness (tab was "Map", route `/wellness`) | `GET /me/map` | spiritual first; social 1.9 low |
| Focus (automatic: the UI has no questionnaire; sign-in sets the weakest dimension and lands on Today, `/next`) | `POST /me/focus {"dimension":"social","barriers":["no_time","dont_know_anyone"]}` | rung 2 |
| Next | `GET /me/next` | Commuter lunch and board games, Tue 12:30, 14 going, fits Tuesday gap |
| I'm in | `POST /commitments {"rec_id": …}` | plan + invite link + reminder 12:15 |
| Friend | `POST /invites/{token}` | with_friend = true (challenge counts double) |
| Skip | `POST /demo/skip-ahead {"to":"next_due"}` | reminder fires |
| Skip | same | follow-up fires |
| Rate | `POST /followups/{id} {"went":true,"helped":4}` | Arc credit (mock), Newark cup +2, next rung 3, "You enjoyed game-based events" |
| Next week | `POST /demo/clock {"now":"2026-10-19T09:00:00-04:00"}` then `GET /me/next` | Pickup basketball, Thu 12:30, rung 3, reason cites the memory |
| Retake | clock to `2026-10-27T09:00:00-04:00`, `GET /me/map` | social 2.4 |
| Taylor | session taylor, `GET /me/next` | person first (CAPS), no events pushed |
| Chat | `POST /chat {"text": …}` (SSE) | `ui` events frame with real event ids, `done` source `ai` |
| Schedule by chat or voice | ask "remind me about that" (tool `set_reminder`) | same plan + reminder + follow-up as the card's Remind me |
| Card | `GET /items/{id}`, `POST /items/{id}/remind` | detail with map + calendar links; reminder idempotent |
| Voice | `WS /voice/ws`, first frame `{"type":"start","token":…}` | `ready`, then transcripts, `audio` (24 kHz PCM16), `ui` frames |

## If something breaks
| Symptom | Do |
|---|---|
| Bedrock slow or erroring | `POST /demo/force-templates {"on": true}`: templates and the code lexicon carry everything |
| Database down | Nothing: student routes fall back to fixtures automatically (header `X-Compass-Fallback: fixture`) |
| Whole API down | Run locally in fixture mode: `MODE=fixtures uvicorn app.main:app` and point the frontend at it |
| Chat or voice can't reach the guardrail, knowledge base or email | Check AWS credentials and Bedrock/Lambda access in us-east-1 (the assistant region); event wording needs us-west-2 too |
| Chat model slow or erroring | Answers fall back to the deterministic responder (`done` source `fallback`); force-templates also forces it |
| Voice fails (mic denied, WS blocked, Nova Sonic error) | Tap "Type instead": the same question works in Chat. Stage demo never depends on voice |
| Stage needs no network | `/present`, press O: offline replay of the recorded run (recorded before the Wellness rename and the questionnaire skip, so it shows the old flow) |
| Wrong state | `POST /demo/reset` |
| Need logs | CloudWatch log group `/compass/api` (JSON lines, request ids, no free text) |
| Redeploy | `python -m scripts.deploy --skip-base` (~6 min); web: `python -m scripts.deploy --web` |
