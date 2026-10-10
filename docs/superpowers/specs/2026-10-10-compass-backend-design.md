# Compass backend: design spec

Date: 2026-10-10 (Sat, Rutgers Health Hack). Owner: backend/data/AWS. Status: awaiting approval.
Inputs: `handoff/COMPASS_BACKEND_BRIEF.md` (engineering source of truth), the v2 product plan (product source of truth), the bundle under `handoff/`.

## 1. Understanding

**What the team asked for (from the brief):** the backend, data and AWS for Compass, the layer that turns existing Wellness Inventory scores into one next step a student takes, follows up, and feeds staff aggregates. The frontend (React, mobile-first) builds against our API. The demo cannot fail.

**What you added in chat:** research deeply, pick the stack, build it. Use Grok 4.7 on Bedrock because you believed Claude is disabled. One approval for spec + plan, then I build and report at gates.

**What I verified (Sat 19:30 ET, account 204762614174, Workshop Studio `WSParticipantRole`, us-west-2):**

| Fact | Result |
|---|---|
| Grok 4.7 (`us.xai.grok-4.7`) | Works. Always reasons. One short sentence: 7.7 s at `reasoning.effort=low`, 11-12 s default, ~550-900 output tokens. `none` rejected |
| Claude Haiku 4.5 (`us.anthropic.claude-haiku-4-5-20251001-v1:0`) | Works, ~1.0 s |
| Claude Sonnet 4.6 / 4.5 / 5 | Work, 1.2-2.3 s |
| Claude Haiku 5.5, Sonnet 5.5, Opus 4.8 | Denied (marketplace / role) |
| Nova 2 Lite, Nova Micro | Work, ~0.5 s |
| gpt-oss-safeguard-20b | Works, ~0.4 s |
| Cohere Embed v4 (`us.cohere.embed-v4:0`), Cohere Rerank 3.5 | Work (multilingual) |
| App Runner | **Denied** |
| ECS, ECR, ALB, CloudFront, ACM, RDS (PG 17/18), Lambda, API GW, EventBridge Scheduler, Secrets Manager, SSM, Location, Guardrails, CloudFormation, CodeBuild, Amplify | List calls allowed |
| Wellness Calendar API | 200 with browser-like UA; 58 events, 2 pages, `next_rest_url`; venues have no geo; cost blank on 43/50; `modified` present; recurrences are separate ids |
| Bedrock Guardrails content filters | Hate, Insults, Sexual, Violence, Misconduct, Prompt attack. **No self-harm category** |

Assumptions (correct me): submission Sun 12:00 ET; the Workshop Studio account lives through judging; teammates host the frontend on Amplify; no real student data ever.

## 2. Non-negotiables carried into every section

Deterministic, explainable core. Safety rules 4.3 and 4.9. Strict per-student isolation. Student can see and delete everything. Synthetic stays labelled. Student flow works with Bedrock down. Ships by Sunday morning.

## 3. Stack

| Layer | Choice | Why |
|---|---|---|
| Language/API | Python 3.12, FastAPI, Pydantic v2 | OpenAPI generated from the same models the handlers return, so fixtures and live responses cannot drift. Brief and bundle are Python |
| DB access | psycopg 3 (async pool), plain SQL in small repository modules | The interesting logic lives in SQL views and pure Python; an ORM adds nothing |
| Migrations | Numbered `.sql` files + 40-line runner with `schema_migrations` table | Readable at 3 a.m.; `schema_v2.sql` is migration 001 |
| DB | Postgres 16 + pgvector (local: `pgvector/pgvector:pg16`; AWS: RDS PostgreSQL 16, `db.t4g.small`) | Given |
| Models | Bedrock Converse via boto3, one `llm` module with per-purpose model routing, timeouts, Guardrails and cache | See section 5 |
| Push | `pywebpush` (MPL-2.0, used unmodified) + VAPID | Standard |
| Tests | pytest + httpx ASGI client against a real Postgres (testcontainers-free: docker compose service) | Real SQL views must be exercised |
| IaC | AWS CDK (Python) | Readable, one `cdk deploy`. Fallback if bootstrap is blocked: boto3 deploy script (decided at build, logged) |
| Packaging | One Docker image; commands `api`, `seed`, `reset`, `ingest`, `worker` | Same image for service, one-off tasks and scheduled ingestion |

## 4. Architecture

```
            Wellness Calendar API ─┐ (hourly, incremental on `modified`)
 ScarletWell list / NWK+CMD research ─┤
                                      ▼
   EventBridge Scheduler ──► ECS task `ingest` ── tag (Grok 4.7 / Haiku) ── geocode (Amazon Location, cached)
                                      │
                                      ▼
 ┌──────────────────────── RDS PostgreSQL 16 + pgvector ─────────────────────────┐
 │ scores (imported) · KB + tags · profiles · memory · plans/invites/feedback     │
 │ notifications · wins · safety_events (no text) · staff views (n>=10, RO role)  │
 └───────────────────────────────────────────────────────────────────────────────┘
                                      ▲
 CloudFront (HTTPS) ─► ALB ─► ECS Fargate service `api` (FastAPI, 1+ warm task)
                                │  ├─ safety: lexicon ─► classifier (Haiku ∥ safeguard) ─► fixed crisis card
                                │  ├─ engine: filters ─► fit score ─► memory adjust ─► diverse top 3 + reasons
                                │  ├─ wording: cache ─► template now; Grok/Haiku in background ─► grounding check
                                │  ├─ loop: commit · invite · reminder · follow-up · Arc mock · challenge
                                │  └─ dispatcher: due notifications by simulated clock ─► web push (budget, quiet hours)
                                ▼
        Frontend (Amplify) · invite page (public) · Staff Pulse (aggregate views only) · The Arc (mock: "attended")
```

Secrets Manager: DB credentials (RDS-managed), VAPID private key, demo signing key. CloudWatch Logs: JSON lines with request id, route, status, latency, fallback flags. No free text, no scores in logs.

## 5. Where models are used, and which

Rule: models label, tag, moderate and write wording from facts code already chose. Nothing safety-critical or score-critical depends on a model.

| Job | Inline? | Primary | Fallback chain | Timeout |
|---|---|---|---|---|
| Crisis classifier (stage 2) | Yes | Claude Haiku 4.5 **and** gpt-oss-safeguard-20b in parallel; take the most severe label | either fails/times out → `concern` if text non-trivial | 1.5 s |
| Barrier text → chips | Yes, parallel with classifier; discarded unless label `none` | Haiku 4.5, enum-constrained JSON | keyword map | 1.5 s |
| Wins moderation | Yes | rules, then Haiku 4.5 labels | model unavailable → `held` for staff (fail safe) | 1.5 s |
| "Why" one-liner, if-then plan | **No.** Served from cache; miss → template immediately, generation queued | **Grok 4.7** (`reasoning.effort=low`) | Haiku 4.5 → template | 20 s / 3 s |
| KB tagging at ingestion | No (batch) | **Grok 4.7**, JSON validated against enums | Haiku 4.5 → keyword tagger | 30 s |
| Ask box / staff ask / voice (P2) | Yes | Haiku 4.5 | template answer from retrieval | 3 s |
| Embeddings (P2 search) | Batch + query | Cohere Embed v4 (1024 dims, multilingual) | keyword search only | 1 s |

Grok 4.7 earns its place where latency does not matter and quality does: wording and tagging, all pre-generated. Inline calls use Haiku 4.5 because 8-12 s would break the 1.5 s p95 target. Every model id is config, so swapping is one env var.

**Grounding check on every generated line** (because Sonnet invented "classes don't start until 2pm" in my probe): reject output that contains any time, number, price, place or weekday not present in the facts given; reject banned words (scores, clinical terms, crisis words); length cap. Rejected → next model → template.

**Guardrails:** one guardrail `compass-guardrail`: denied topics (diagnosis, medication advice, self-harm methods), PII filters (name, email, phone, address: anonymize on output, block on input for wins), prompt-attack filter on input, content filters (hate, insults, violence, misconduct). Attached via `guardrailConfig` on Converse where the model supports it; otherwise `ApplyGuardrail` on input and output. External text (calendar descriptions) is wrapped as data with an instruction that it is untrusted.

## 6. Data model (changes to schema_v2)

Kept: everything in `schema_v2.sql`. Added/changed (migrations 002+):

- `app_clock` (global simulated now) and `demo_sessions(token, student_id|null, role, sim_now, created_at)`. Per-session clock overrides global.
- `profiles`: `free_windows` stays `text[]` ("Tue 12:20-14:30"), add `rung_reason`, `language`.
- `kb_items`: add `phone, hours_text, open_hours jsonb, url, source_url, verified_on, summary_es, modified_at, demo_pin, series_key, formats text[]`. `cost` stays `free|paid|unknown`.
- `kb_tags.tag_type`: add `barrier`, `format`.
- `recommendations`: add `set_id, rank, reasons jsonb, engine_version, pushed boolean`.
- `student_memory(id, student_id, kind, key, statement, statement_es, source_type, source_ref jsonb, confidence, used_for, created_at, updated_at, last_used_at)`, unique `(student_id, kind, key)`, cascade delete.
- `notifications`: add `commitment_id, status` values `held_budget|held_quiet`, `payload jsonb`.
- `wins.status`: add `held`; add `moderation_code`.
- `safety_events.level`: add `concern`. Never stores text.
- `crisis_lines`: add `campus_code, kind (call|text|web), contact, language, sort, verified boolean`.
- `llm_cache(key, purpose, model, lang, text, created_at)`, keyed by hash of the facts (not student id).
- `geocode_cache(address, lat, lon, provider, fetched_at)`, `ingest_runs`.
- `challenges`: add `group_size`, per-campus rows for the campus cup.
- DB roles: `compass_app` (owner of data), `compass_staff_ro` (SELECT on staff views and EXECUTE on staff functions only). Staff endpoints and "ask the data" connect as `compass_staff_ro`. Suppression (n>=10) lives inside views/functions.

"Forget me" = `DELETE FROM students WHERE id=$1` (cascades), plus `safety_events.student_id` set null and wins `student_id` set null. Tested.

## 7. Next-step engine (`engine/`), pure function

`rank(student_ctx, items, stats, memory, now, config) -> RankResult`. No I/O inside; same inputs + same clock = same output.

**Hard filters** (each produces a reason code): campus match or online; occurs or is open inside a free window within `horizon_days=10` (students with no windows: any time in horizon; resources with unknown hours pass with `hours_unknown` reason and window score 0.5, never invented hours); free if `free_only` (cost `unknown` passes with a "cost not listed" reason); not declined; not past (by simulated clock); sample events only on their campus and flagged `synthetic`.

**Fit score** (weights in `config/engine.yaml`):

| Component | Weight | Definition |
|---|---|---|
| dimension | 0.35 | 1.0 if tagged with focus dimension (× tag confidence); 0.7 if it addresses a root cause linked to the focus via the student's barrier (`coursework → academic_workload` counts for physical/sleep and emotional); else 0 |
| barrier | 0.25 | share of tapped barriers the item addresses (barrier→cause/format map in config) |
| window | 0.20 | share of the event (plus walk buffer) inside the window; 1.0 = fits snugly |
| rung | 0.10 | 1.0 at target rung, 0.5 one below, 0 above |
| helped_similar | 0.10 | Bayesian average of "helped ≥4" for the student's cohort (campus × housing) on this item or its series, Beta prior from the campus mean, only feedback dated ≤ now; reported with n |

**Memory adjustment:** each active memory fact may add or subtract up to `0.05`, total capped at ±0.10, and each one appears as a reason with its memory id. Deleting the fact removes the reason.

**Distance:** walking minutes from the student's campus anchor (haversine × 1.3 at 80 m/min). Penalty 0.01 per 5 minutes beyond 15. Final sort `(-score, walk_min, item_id)`.

**Output:** pick + 2 alternates chosen greedily so each differs from the ones already chosen in at least two of {kind, venue, weekday, rung, series}. Each carries item details, time, place, walk minutes, cost, rung, going count (only if ≥5, else "a few"), filters passed, component scores, memory reasons, `why` line, `why_source` (`ai|template`).

**Social ladder:** `dont_know_anyone` sets target rung 2 ("structured: you'll be playing, not mingling"); otherwise 1 for new students. After a step rated 4-5 the target rises one rung (max 3) and the follow-up response offers it.

**Care-first** (rule in `safety/care_first.py`, thresholds in config): emotional ≤ 1.6, or emotional < 2.3 and ≥ 3 other dimensions < 2.3. Then card 0 is human support for the campus (counselling, teletherapy, peer community) with crisis lines; events still returned with `pushed=false`; no automatic reminders for unpushed events; gentler push copy. Logs a `care_first` safety event with no scores.

**Never empty:** fallbacks in order: open-hours place, online option, 10-minute micro-step from a static table per dimension (`kind=micro`).

**Learning (7.3) without losing determinism:** helped_similar is a Beta-Binomial posterior mean (explainable: "rated 4+ by 71% of 41 Newark commuters"). Thompson sampling is implemented behind `engine.explore=false`; when on, the sample is seeded by `(student, week)`, so it stays reproducible. Demo runs with exploration off.

## 8. Safety layer (`safety/`)

Runs on every free-text input (barrier text, wins, Ask box, voice) before anything else touches the text.

1. **Normalize:** lowercase, Unicode NFKC, strip accents (keep a Spanish copy), collapse repeated letters, map leetspeak, keep emoji.
2. **Stage 1 lexicon** (`safety/lexicon.yaml`): crisis phrases (direct, indirect, slang, Spanish, method words like overdose amounts and pill emoji, per Crisis Text Line's published finding that method words predict risk more than the word "suicide"), concern phrases, and idiom allowlist ("this exam is killing me", "dying to", "dead tired"). An idiom match only downgrades when no other crisis cue is present.
3. **Stage 2 classifier:** Haiku 4.5 and gpt-oss-safeguard-20b in parallel; label ∈ {crisis, concern, none}; the more severe wins. Timeout/error → `concern` unless the text is trivially short/empty.
4. **Outcome:** `crisis` → fixed crisis response built only from `crisis_lines` rows for the student's campus (no model output), nothing else in the response, safety event logged without text, input not stored. `concern` → request proceeds but response includes a gentle "people you can talk to" block and free text is not used for barrier mapping. `none` → proceed.

**Test set:** `tests/safety/phrases.yaml`, ≥ 60 crisis/concern phrases (direct, indirect, slang, Spanish, method words) and ≥ 25 false-alarm phrases. Requirement: **stage 1 alone catches 100% of the crisis set**, so the test passes with Bedrock blocked; the classifier adds coverage for phrasings we did not anticipate. False alarms measured and reported (target ≤ 10%, idioms must pass). Runs in CI and in the smoke test through every free-text endpoint.

**Crisis lines** (seeded, `verified=false` until a human calls each): 988 (call/text; Spanish: press 2, text AYUDA), Crisis Text Line 741741 (keyword conflicts across sources: HOME/TALK/HELLO; to verify), 911, NB CAPS 848-932-7884 (after-hours via prompts), Newark Counseling 973-353-5805 and Uwill crisis 833-646-1526, Camden Wellness 856-225-6005 and Uwill 833-646-1526, NJ Hopeline 855-654-6735. A call-down sheet ships in `docs/crisis_lines_verification.md`. Unverified rows show a `verify` flag in non-prod only.

## 9. Student memory (7.1)

Decision: **self-managed, typed, bounded profile facts in Postgres, written mostly by rules.** Borrowed: Hermes (small bounded store, no silent eviction, user can inspect and remove), OpenClaw (`USER.md` facts superseded in place, not contradicted; curated layer separate from logs), mem0 (ADD/UPDATE/DELETE/NONE semantics, done here deterministically by `(kind,key)` upsert instead of an LLM call). Rejected: AgentCore Memory (extracts from conversations we deliberately do not have; async; harder to prove deletion; noted as pilot option), mem0 runtime (LLM on every write), Letta (server to run), Honcho (AGPL).

- **Kinds:** `likes_format` ("You enjoyed game-based events"), `disliked_format`, `time_works` ("Tuesday midday works for you"), `helped` ("Tutoring helped you"), `declined` (item-level; deleting un-declines), `constraint` (from barrier text, closed vocabulary: `works_evenings`, `long_commute`, `caregiving`, …), `rung` ("Ready for open social events").
- **Writers:** rules on taps and feedback (primary). A model only maps barrier text to the closed `constraint` vocabulary after the crisis check; raw text is never stored.
- **Never stored:** scores or bands (they stay in score tables), moods, health, safety events, raw text, friends' details, locations.
- **Bounds:** max 25 learned facts; contradictory evidence updates confidence or deletes (helped 2 after helped 4 on the same format → fact removed).
- **Ranking use:** adjustments in section 7, each cited by memory id in reasons and stamped `last_used_at`.
- **API:** `GET /me/memory` returns profile facts (focus, barriers, windows, language) plus learned facts, each `{id, kind, statement, source:{type, label, at}, used_for, learned_at, last_used_at, deletable}`. `DELETE /me/memory/{id}`, `DELETE /me/memory`, `DELETE /me` (forget me).

## 10. Commitment lifecycle and notifications

`POST /commitments` → plan text (if-then, from cache or template), `.ics` link, reminder time, invite link. Invite = random token; public page shows event only; "I'll come too" needs no account and marks the commitment `with_friend`.

**Scheduler (7.5):** notifications are rows. The dispatcher sends rows due at the simulated now: a background loop every 30 s in the API task (Postgres advisory lock so one sender), plus synchronous dispatch from skip-ahead. Rules from the evidence: at most 3 pushes/student/ISO week (config); quiet hours 22:00-08:00 shift to 08:00; one reminder per plan at start − 15 min (skipped if already past); one follow-up after the event end (+2 h default, configurable for the "2 days later" story); weekly pick and retake nudges only on fresh-start days (Monday, 1st of month, week after midterm window), retake nudge at most once per 4 weeks, never a third unanswered nudge for the same thing (Oregon State). Over budget → `held_budget`, delivered in-app via `GET /me/inbox`. Care-first students get no event pushes. Copy is templated and lock-screen safe; a test asserts no score, mood or crisis word can appear in any notification template.

**Skip-ahead:** `POST /demo/skip-ahead {to: "next_due" | iso_datetime | "+2d"}` advances the session clock, dispatches everything due, returns `{fired:[...], now}`.

**Follow-up side effects:** `went` → Arc credit via `ArcAdapter.record_attendance(pseudonymous_id, arc_activity_id, occurred_at)` (mock writes `arc_credits` status `mock`); challenge step (weight 2 with a friend); memory update; next-rung suggestion when helped ≥ 4.

## 11. Social layer

Going counts from the view (≥5, else "a few"). Challenges cooperative, per group, goal sized to group, hidden if group < 10. Wins: crisis check → rules (names via capitalized-name heuristic + first-name list + @handles, contact regex, insult list, advice patterns) → Haiku label → `approved | held | rejected | routed_to_care`. "Same here" is the only reaction (idempotent per session).

## 12. Staff aggregates

Endpoints read only through `compass_staff_ro`: funnel (campus × dimension), gaps (need vs supply), weekly averages with population filters (level, first_gen, housing), dips (week ≥ 0.15 below its trailing 4-week mean, computed in SQL), retakes (Compass users vs non-users). Responses carry `synthetic: true`, `suppressed_groups: n`, and calendar overlays (real fall 2026 dates + labelled approximate midterm window).

## 13. Ingestion

`compass ingest`: Wellness Calendar via `next_rest_url` pagination, browser-like UA identifying Compass, upsert by event id, skip unchanged `modified`, HTML/entity cleanup, blank cost → `unknown`, all-day and virtual handled, iCal fallback. ScarletWell list parsed (starter logic kept). Newark/Camden research items from `data/research/nwk_cmd_resources.yaml` (each with address, hours, phone, source URL, verified date; no invented hours). **Scarlet Sync** (`https://scarlet-sync-backend-1086246455189.us-east1.run.app`, a student-built public API you pointed me to; checked 19:50: 336 upcoming events): adapter `ingest/scarlet_sync.py` pages `/events?limit=100&offset=`, snapshots into our DB (no live dependency during the demo), keeps `source_url` and attribution "via Scarlet Sync". Kept: `recreation`, `imleagues` (intramurals → physical/social, rung 2-3), `getinvolved` (club meetings → rung 3; see open question), `newbrunswick`, `mason_gross`. LibCal study-space room slots (165) are collapsed into one "study space" place per library with open hours (Dana Library Newark, Robeson Library Camden, NB libraries) so they serve as real open-hours fallbacks without flooding the KB. Dropped: away athletics games and non-http URLs. Their API code is not copied; only their public data is read, politely, at most hourly. Geocoding: Amazon Location (Places), cached per address; Nominatim fallback at 1 req/s. Tagging: Grok 4.7 batch with validated enums and confidences; `tagged_by='staff'` rows are never overwritten. Schedule: EventBridge Scheduler hourly → ECS RunTask.

## 14. API contract (v1)

All responses: `synthetic: bool`, `now` (simulated, America/New_York ISO), and on fallback header `X-Compass-Fallback: fixture|template`. Auth: bearer demo-session token from `POST /demo/session`.

| Method | Path | Notes |
|---|---|---|
| POST | /demo/session | `{persona: andre|priya|taylor|sofia|jordan|staff, now?}` → token, now, student summary |
| GET | /demo/personas | list for the persona switcher |
| POST | /demo/clock | set session now |
| POST | /demo/skip-ahead | see section 10 |
| POST | /demo/reset | exact demo start state |
| GET | /me/map | 8 dimensions with band, total, strengths first, care_first, trend (takes ≤ now) |
| POST | /me/focus | `{dimension, barriers[], text?, free_only?}` → profile or `crisis` response |
| GET | /me/next | `{care_first_card?, pick, alternates[2], crisis_lines}` |
| POST | /me/next/{rec_id}/decline | `{reason: swap|not_now}` → next best set |
| GET | /me/card | compact MyRutgers card |
| GET / DELETE | /me/memory, /me/memory/{id} | section 9 |
| DELETE | /me | forget me |
| GET | /me/inbox | in-app notifications |
| POST | /commitments | `{rec_id, plan_text?}` → plan, ics_url, reminder_at, invite_url |
| GET | /commitments/{id}/ics | calendar file |
| GET / POST | /invites/{token} | public |
| POST | /followups/{commitment_id} | `{went, helped?}` → progress delta, arc, challenge, next_rung |
| GET | /pulse | challenges, approved wins |
| POST | /wins, /wins/{id}/same-here | moderation pipeline |
| GET | /push/vapid-key | public key |
| POST / DELETE | /push/subscriptions | store/revoke; 404/410 from push service revokes |
| GET | /staff/funnel, /staff/gaps, /staff/weekly, /staff/dips, /staff/retakes | aggregates |
| GET | /health | liveness + readiness per dependency (db, bedrock, push) |
| P2 | /ask, /staff/ask, /v1/chat/completions | scoped, crisis-checked |

Contract file `contract/openapi.json` is generated from code and committed; `contract/CHANGELOG.md` records every change for the frontend.

**Fixture mode:** `COMPASS_MODE=fixtures` serves `fixtures/{persona}/{route}.json`. Automatic fallback: if the DB is unreachable on a student/demo route, the fixture is served with the header. Fixtures are first hand-built from the Pydantic models (validated in tests), then re-recorded from the live API (`compass fixtures record`) so shapes always match.

## 15. Demo determinism

Reset truncates all tables and reloads packaged seed files with fixed ids; `llm_cache` is kept and pre-warmed. Global clock default `2026-10-12T09:00-04:00` (Monday, fresh start). Pinned sample events (labelled `synthetic`, `demo_pin`):

| Persona | Expected |
|---|---|
| Andre | Focus social, barriers no_time + dont_know_anyone → "Commuter lunch and board games (sample)", Paul Robeson Campus Center, Tue Oct 13 12:30-13:30, rung 2. Reminder Tue 12:15. Follow-up after. Rated 4 → memory "You enjoyed game-based events" + "Tue/Thu midday works", rung → 3. Skip to Mon Oct 19 → "Open gym pickup basketball (sample)", Golden Dome, Thu Oct 22 12:30, **rung 3** (persona file said 2; changed so "next rung" holds; logged). Skip to Oct 26 → take 2 visible, social 2.4 |
| Priya | Focus physical, barrier coursework → Busch Learning Center (real, 118 Frelinghuysen Rd), reason "addresses what's cutting into your sleep" |
| Taylor | care_first → card 0 CAPS NB + Uwill/Togetherall + crisis lines; events `pushed=false` |
| Sofia | Camden financial → real food pantry / financial aid / online; Spanish templates |
| Jordan | social, rung 1-2 → NB pick + Livingston residence-hall challenge (added, group ≥ 10) |

## 16. Resilience

Bedrock blocked → every student endpoint still answers (templates, lexicon, keyword barrier map, wins held). DB down → fixtures. Each model call: hard timeout, one retry for idempotent batch only, circuit breaker (3 failures → skip model for 60 s). `/health` reports each dependency. A `FORCE_TEMPLATES=1` switch for the stage.

## 17. AWS

us-west-2 (creds default and all needed models). Tags `project=compass` on everything.
- Default VPC. RDS PostgreSQL 16 `db.t4g.small`, 20 GB gp3, encrypted, not public, SG only from the ECS SG, RDS-managed secret.
- ECR repo; ECS Fargate cluster; service `api` (0.5 vCPU / 1 GB, desired 1, public IP in default subnets to avoid NAT cost); ALB on HTTP; **CloudFront** in front for HTTPS on `*.cloudfront.net` (no domain needed), caching disabled, all methods, Authorization forwarded, ALB ingress restricted to the CloudFront origin-facing prefix list + secret origin header.
- EventBridge Scheduler hourly → ECS RunTask `ingest`.
- Task role: `bedrock:InvokeModel*`, `bedrock:ApplyGuardrail`, `geo:*` places read, secrets read.
- Image build: local Docker (needs Docker Desktop running) or CodeBuild fallback.
- Credentials: Workshop Studio session creds expire. Deployed services use IAM roles and keep running; only my deploys need fresh creds.

## 18. Testing and acceptance

Unit: engine (pure, table-driven per persona), care-first, lexicon (full phrase set), grounding check, notification rules (budget, quiet hours, fresh start), memory upsert/contradiction, moderation rules. Integration (real Postgres): every route, forget-me cascade, staff suppression (no group < 10 can be returned even with crafted filters), reset exactness (hash of table contents before/after). Contract: every fixture validates against its response model. Smoke `scripts/smoke.py BASE_URL`: section 9 scenarios end to end, Bedrock-blocked mode, latency p95 report. Latency targets: student p95 < 1.5 s with cached wording, staff < 1 s.

## 19. Risks

| Risk | Mitigation |
|---|---|
| Workshop account blocks IAM role creation for CDK | Detect in first deploy step; fall back to boto3 script with pre-allowed roles; worst case ECS on EC2 is not needed, Lightsail containers as last resort |
| Docker Desktop not running | You start it; CodeBuild fallback |
| Grok slow/failed | Pre-generation + Haiku + templates; never inline |
| Newark/Camden research takes long | Time-boxed; start with the 4 known items, fill to ~30 with verified sources only |
| Crisis numbers unverified | Call-down sheet; flag stays visible until a human verifies |

## 20. Out of scope

UI, service worker, deck, demo script. Real SSO. Real Arc integration. Email digest (SES sandbox) unless time remains.
