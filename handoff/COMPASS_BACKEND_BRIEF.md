# Compass: Backend, Data and AWS Brief

**You own:** the backend, the data, and everything on AWS.
**Teammates own:** the frontend (a mobile-first React web app) and the pitch. They build against your API.
**Hard deadline:** project submission Sunday Oct 11, 2026 at 12:00 ET, judging at 1:00 pm. This comes from another team's notes; confirm it with the organizers and tell us if it's different.
**Written:** Saturday Oct 10, about 7 pm ET. About 17 hours remain.

You're trusted to make engineering calls. This brief explains what we're building, why, what "done" means, and where the traps are. It deliberately doesn't tell you how to write the code. When something here conflicts with good judgment, use your judgment and tell us what you changed.

---

## 0. TL;DR

- **Product:** Compass turns a Rutgers student's existing Wellness Inventory scores into one next step they actually take. The step is a real event or resource that fits their week, ideally taken with a friend. Afterwards Compass asks "did it help?", shows progress, and nudges the student to retake the inventory at the next fresh start.
- **The problem:** student engagement. Rutgers already has the tools: the inventory, event calendars, The Arc (Suitable), counselling, tutoring. Students who need them most don't use them. Compass is the layer between those tools, not another destination app.
- **Your job:** the data model, the next-step engine, the safety layer, the AI calls on Amazon Bedrock, reminders and follow-ups, the social mechanics, the staff aggregates, data ingestion, and an HTTPS deployment on AWS.
- **First thing (target ~90 minutes):** publish the API contract with working fixture responses, so the frontend can start in parallel.
- **The prime directive:** the live demo cannot fail. Every endpoint needs a fixture fallback. Every AI call needs a timeout and a template fallback. The clock must be controllable.
- **The second directive:** safety-critical and score-critical logic is plain, deterministic code. AI only labels, tags, moderates and writes wording from facts the code already chose.
- **The third directive:** several design questions are deliberately left open for you: how Compass remembers each student, whether any part deserves an agent loop, how ranking learns, how crisis detection works. Research how the best open-source projects solve them, then decide (section 7). We'd rather you build on proven open-source work than reinvent it.

---

## 1. Context

### The event
- **Rutgers Health Hack 2026**, at RWJ Medical School, Fri Oct 9 to Sun Oct 11. Sponsors are AWS, Microsoft and Sevaro, so AWS-native architecture is a plus.
- **Track:** "Wellness, Reimagined", Challenge 1: a student-facing app combining the Wellness Inventory with personalized, geo-located resources, with special attention to the Newark and Camden campuses. We also cover the core of Challenge 2, a staff view of wellness trends and resource gaps. Both briefs are in the bundle.
- **Judging criteria:** innovation; technical implementation (code, cloud architecture, data integration); impact; presentation; feasibility and scalability.
- **Judges and mentors:**
  - Dr. Margaret Swarbrick, ScarletWell director, whose 8-dimension wellness model underlies the inventory.
  - Dr. Leslie Lenert and Dr. Antonina Mitrofanova, BMIHAI, Rutgers' biomedical informatics and health AI center.
  - ScarletWell staff, and two student advisors.

### What the mentors told us on Saturday (this reshaped the product)
1. **Focus on one problem: engagement.** That means students using resources, coming back, feeling they belong, and retaking the inventory.
2. **Skip the questionnaire.** Students already take the Wellness Inventory in the MyRutgers portal. Assume we receive their scores. The organizers have a de-identified dataset; until we get it, we use synthetic data, which is in the bundle.
3. **"They already have Suitable, the Rutgers portal, ScarletWell... why another app?"** Our answer: Compass isn't one. It's a layer that reads the scores, picks from existing calendars and services, follows up, and credits The Arc.
4. **Safety worries about AI, guardrails and extreme cases.** We dropped speech-to-speech AI (Amazon Nova Sonic) for that reason. There is no open-ended "companion chat". Crisis handling is code, not a model.
5. Reported second-hand from another team's notes: Dr. Swarbrick called today's inventory "very static" and wants retakes, trends, events on a map, aggregate views, and Newark and Camden coverage. A student advisor said **"closest is not always best"**: rank by fit first, distance second.

### The product loop
1. **Scores arrive.** The student sees their 8 dimensions, strengths first.
2. **They pick one area** to grow this month.
3. **They tap what gets in the way:** chips like "I don't know anyone", "no time between class and work", "money", plus optional short text.
4. **Compass offers one step** that fits their free windows, campus, cost and "social rung", with two alternates and a one-line "why".
5. **"I'm in".** Compass writes an if-then plan, adds a calendar entry and a reminder, and creates a share link to invite a friend.
6. **The reminder** arrives at the right moment.
7. **"Did you go? Did it help?"** Two taps. Progress shows on the map, a credit goes to The Arc (mocked), and the campus challenge bar moves.
8. **Next week** brings the next rung. At fresh starts (Mondays, the 1st of the month, after midterms) Compass nudges a retake in MyRutgers, and new scores flow back in.

**Care-first branch:** if scores are very low, the first card is a person (counselling, teletherapy), not an event.

### Source-of-truth documents
- **Product plan (v2, current):** https://claude.ai/code/artifact/2bcbad2e-9657-40ec-ab1d-d7e3b8ba48b2. Read the TL;DR, "The product", "Social layer", "Safety", "Where AI is used", "Staff Pulse" and "Build plan". If this brief and the plan disagree on product behaviour, the plan wins; on engineering, this brief wins. The plan's build section lists an agent loop and AgentCore memory as "cut". That was a time-saving call made before you joined; section 7 reopens both questions for you.
- **First plan (v1, reference only):** https://claude.ai/code/artifact/9520146f-7216-4a3f-8508-785551d57373. Useful for the Wellness Calendar API notes, web push on iPhone, and crisis-line research. Its questionnaire flow is obsolete; treat its other design choices as one earlier take, not decisions.

### What's in your bundle
| Path | What it is |
|---|---|
| `briefs/` | Challenge 1 and Challenge 2 text from the organizers |
| `data/` | The synthetic dataset, its README, the generator and loader scripts, and `schema_v2.sql`. Loaded and checked in Postgres 16 with pgvector |
| `kb/ingest.py`, `kb/items.json`, `kb/scarletwell.txt` | Knowledge-base starter: pulls the live Wellness Calendar, parses ScarletWell's resource list, writes 116 real items. Tagging is keyword-based and should be replaced |

Treat all of it as a head start, not a constraint. Rewrite whatever you want.

---

## 2. Scope

**You own**
- Data model and migrations. Start from `schema_v2.sql` and change what you need.
- Seed data: synthetic students, personas, real KB items, sample Newark and Camden events, challenges, wins.
- Ingestion: the live Wellness Calendar, ScarletWell resources, newly researched Newark and Camden resources, geocoding, AI tagging.
- The next-step engine (ranking) and its explanations.
- The safety layer: crisis check, care-first rule, moderation, Guardrails.
- All Bedrock calls, and the choice of any agent framework.
- Personalization memory: what Compass learns about each student over time, how it's kept, how the student sees and deletes it. The design is yours; see section 7.
- The commitment lifecycle: plans, invites, reminders, follow-ups, feedback, Arc credit (mock), challenge progress.
- Notifications on the server side: web push sending and subscription storage; email optional.
- Staff aggregates for the Staff Pulse screen.
- AWS infrastructure, deployment, secrets, logging.
- Demo controls: simulated clock, persona switching, skip-ahead, reset.
- The architecture diagram and a 5-line "how it's built" for the deck.

**You don't own:** the UI, the service worker, the deck, the demo script. You are the frontend's most important dependency, so unblock them early and don't change the contract silently.

---

## 3. Deliverables by priority

### P0: the demo depends on these
1. **API contract plus fixture mode, first.** An OpenAPI spec and a server that returns realistic fixture responses for every endpoint, deployed or easy to run, within about 90 minutes. Fixtures must match the real response shapes.
2. **Database seeded** with the synthetic semester, the 5 personas, the real KB items and the sample events. One command to reset to a known demo state.
3. **Student flow endpoints, live:** the map, focus and barriers, next step, commit, invite, follow-up, campus pulse. See section 5.
4. **Next-step engine:** deterministic, explainable, config-driven weights. It returns the reasons behind each pick.
5. **Safety layer:**
   - A crisis check on every free-text input before any model sees it.
   - A fixed crisis response built from a verified table.
   - The care-first rule.
   - A test set of at least 50 phrases that passes 100%, with false-alarm checks.
6. **AI wording with fallbacks:** "why" lines and if-then plan text from Claude on Bedrock, with strict timeouts and template fallbacks. Pre-generate and cache them for the demo personas.
7. **Reminders and follow-ups** that fire on schedule and can be triggered instantly with skip-ahead. Web push sending works end to end with the frontend's subscription.
8. **Deployed on AWS** behind HTTPS with a stable URL and CORS for the frontend's origin. A health endpoint. A smoke-test script that runs the demo flows against the deployed API.

### P1: makes it convincing
9. **Staff aggregates:** the conversion funnel (suggested → committed → attended → helped), need vs supply by campus and dimension, weekly averages with calendar overlays, dip detection, retake rates. Small groups are hidden at the data layer.
10. **Live ingestion:** an hourly calendar pull, incremental on the source's modified time, with AI tagging (8 dimensions, causes, social rung, solo-friendly, cost) and geocoding with a cache.
11. **Real Newark and Camden coverage:** research and add about 30 verified resources. Each needs an address, hours, phone, the source URL and the date checked.
12. **Social mechanics:** "N going" counts (shown only from 5 up), cooperative challenges with progress, a wins wall with a moderation pipeline, and bring-a-friend invites.
13. **The Arc adapter:** a clean interface with a mock implementation. It records "attended" credit only, never scores.
14. **Student memory, in your design from section 7.1.** Compass visibly learns, for example "you liked structured events", "Tuesdays work", "tutoring helped". The memory shapes the next pick in a way the reasons can show. The student can list and delete everything it holds.

### P2: stretch, only after P0 and P1 are green
15. **Ask box:** retrieval over the KB plus one scoped Claude call. Only questions about resources and events; everything else gets a kind redirect. Crisis check first.
16. **Staff "ask the data":** natural-language questions answered by generated read-only queries over the aggregate views only. Show the query, and keep the small-group protection in force.
17. **Voice via ElevenLabs:** an OpenAI-compatible streaming chat-completions endpoint that ElevenLabs Agents calls as a "custom LLM". It routes every transcript through the same crisis check and scoped logic. No Nova or any other speech-to-speech model.
18. **Spanish:** "why" lines and plan text in Spanish for students who prefer it (persona Sofia).

---

## 4. Product behaviour to implement (spec in prose)

### 4.1 Time is an input
- The demo runs on Sunday, but the story happens across a semester. Build a **simulated clock**: a configurable "now", settable per demo session or globally. Every time-based decision reads it: what's upcoming, free windows, reminders, quiet hours, fresh-start nudges.
- All user-facing times are America/New_York.
- **Skip-ahead** advances the clock and fires whatever became due: the reminder, then the follow-up.

### 4.2 Scores and bands
- Scores come in per take: student, date, 8 dimension scores, total.
- The official scoring and cut-offs aren't known yet. Use placeholders, all in config:
  - each dimension on a 1.00 to 4.00 scale;
  - "low" below 2.3;
  - "high" from 3.2.
- Build the importer so a future ScarletWell export (CSV, possibly item-level) maps in through configuration, idempotently. Never let a model compute or alter a score.

### 4.3 Care-first rule (deterministic, config-driven, placeholder thresholds)
- **Triggers** if the emotional score is 1.6 or below, or if emotional is low and three or more other dimensions are also low.
- **When triggered:**
  - The first card is human support for the student's campus (counselling, teletherapy, peer community), with crisis lines visible.
  - Event suggestions stay available but aren't pushed.
  - Push copy is gentler.
- **Logging:** record that care-first applied, never the scores, outside the student's own records.
- **Language:** this is an offer, not a diagnosis. The inventory measures wellness, not illness. Use no clinical language anywhere.

### 4.4 The next-step engine: fit first, distance second
- **Hard filters:**
  - right campus, or online;
  - happens or is open inside one of the student's free windows in the next ~10 days;
  - free if the student asked for free only;
  - not previously declined;
  - not in the past;
  - sample events allowed only where the dataset intends them.
- **Fit score.** This is a starting point, not gospel: improve it after 7.3, but keep it explainable and deterministic for the demo. Weights live in config so ScarletWell could tune them.

  | Component | Weight |
  |---|---|
  | Matches the chosen dimension | 35% |
  | Addresses the tapped barrier | 25% |
  | Fits the free window snugly | 20% |
  | Right social rung | 10% |
  | Helped similar students | 10% |

- **Distance** is only a tie-breaker, plus a penalty past about a 15-minute walk.
- **The social ladder:**
  - Rung 1: just show up (a talk, yoga).
  - Rung 2: structured (game night, cooking, volunteering).
  - Rung 3: open social (mixers, club meetings).
  - Students who say "I don't know anyone" start at rung 1 or 2. Offer the next rung after a step rated 4 or 5.
- **Output:** one pick plus two alternates that differ meaningfully, not three near-duplicates. Each carries structured reasons: filters passed, the component scores, walking time, cost, the going count if 5 or more, the rung. The frontend renders the reasons, and an AI-written one-liner sits on top. That makes the demo explainable to a judge in one sentence.
- **Determinism:** the same inputs and the same clock give the same pick. Personas must get the picks the demo script expects (section 4.12).
- **Fallbacks when nothing fits:** a place with open hours, an online option, or a 10-minute micro-step. Never an empty card.

### 4.5 Commitments, invites, reminders, follow-ups
- **Lifecycle:** planned → went or missed (or cancelled). Invites are links only: no contacts, no messaging, no friend graph. Someone who opens a link sees the event and can tap "I'll come too" without an account.
- **Reminder:** one per plan, timed sensibly before the start, respecting quiet hours (default 22:00 to 08:00).
- **Push budget:** at most 3 pushes per student per week, configurable.
- **Follow-up:** after the event ("2 days later" in the story, configurable). The answer records "went" plus "helped" on a 1 to 5 scale.
- **Side effects of an attended step:**
  - Arc credit via the adapter;
  - a challenge step, counted double if taken with a friend;
  - an update to "what helped" for this student.
- **Notification copy is lock-screen safe:** never mention scores, moods, struggle or crisis. "Game night starts in 15 minutes", never "Feeling lonely?".

### 4.6 Social mechanics and their guardrails
- **"N students going":** count only. Below 5, show "a few", or the frontend hides it.
- **Challenges:** cooperative, group-level only (campus, residence hall, club). Goals are sized to group size. No individual leaderboards. Groups under 10 are never exposed.
- **Wins wall:**
  - 140 characters, tagged to a dimension.
  - The only reaction is "same here". No comments, no replies.
  - **Pipeline:** crisis check, then moderation, then publish.
  - **Moderation** (rules plus Claude Haiku) catches names, insults, advice-giving and contact details.
  - **A crisis-flagged post is never published.** The poster privately gets the crisis response, and a safety event is logged without the text.

### 4.7 The Arc
- **What it is:** Rutgers' involvement platform, powered by Suitable. It has points, achievements and a "Wellness" competency, check-in by QR code, and a Scorecard students share with employers.
- **No API:** we found no public API, so build an adapter interface with a mock that records credit locally and shows "credit added".
- **Rule:** only "this student attended activity X" may ever leave Compass. Never scores.

### 4.8 Staff aggregates (Challenge 2)
- **Endpoints:**
  - **The funnel** by campus and dimension.
  - **Need vs supply:** students whose latest score in a dimension is low, against items tagged to that dimension on their campus.
  - **Weekly averages** by campus and dimension, plus filters for population (undergrad or grad, first-gen, commuter).
  - **Calendar overlays:**
    - real fall 2026 dates: classes began Sep 1; Thanksgiving recess Nov 26 to 29; classes end Dec 10; reading days Dec 11 and 14; finals Dec 15 to 22;
    - midterms aren't on the registrar calendar, so use a labelled approximate window.
  - **Dip detection:** flag a week 0.15 or more below its own 4-week trailing average, configurable.
  - **Retake rates**, Compass users vs non-users.
- **Small-group suppression:** groups under 10 students are suppressed in the database layer (views or a policy), not only in the UI.
- **Synthetic label:** responses carry a "synthetic" flag while we run on dummy data, so the UI can badge it.

### 4.9 Safety layer
- **Where it runs:** on every free-text input (barrier text, Ask box, wins posts, voice transcripts), before anything else touches the text.
  - **Stage 1:** a curated phrase list, including common slang and Spanish.
  - **Stage 2:** a small classifier call (Claude Haiku) that returns only a label: crisis, concern or none.
  - **If the classifier is unavailable or times out, fail safe:** treat ambiguous text as concern, never as fine.
- **The crisis response is fixed content** from a table of verified lines per campus. No model writes it. The bundle has a list to verify. A human must call or check each number before the demo, and the keyword for Crisis Text Line also needs checking.
- **Never store the text** that triggered a safety event. Never put free text in logs.
- **Bedrock Guardrails on every model call:**
  - denied topics: diagnosis, medication advice, self-harm methods;
  - sensitive-information filters;
  - prompt-attack filters.
  - The standalone guardrail check is a reasonable extra layer on free text, but the code-first check stays primary.
- **Untrusted text:** calendar descriptions and resource text are external content. When you send them to a model (for tagging), treat them as data, and don't let them steer behaviour.
- **The test set:** at least 50 phrases covering direct, indirect, slang and Spanish crisis language, plus false-alarm cases like "this exam is killing me". It runs in CI or the smoke test and must pass 100% before the freeze.

### 4.10 Where AI is used
| Job | How |
|---|---|
| "Why" one-liners and if-then plan wording | Generated from structured facts the engine chose. The model never adds facts. Template fallback; cache per pick |
| Tagging KB items at ingestion | Dimensions, causes, social rung, solo-friendly, cost, each with a confidence. Staff overrides win |
| Classifying barrier text into barrier chips | After the crisis check |
| Moderating wins posts | Rules plus a model |
| P2 work | The Ask box, staff questions, the voice endpoint |

- **Models:** Claude Haiku for labelling and moderation; Claude Haiku or Sonnet for wording; an optional multilingual embedding model on Bedrock for search.
- **Where AI may grow:** if your research in 7.2 convinces you an agent loop belongs somewhere (Ask box, staff questions, voice), that's your call, inside the safety rules.
- **Latency:** the student flow must never wait on a model call longer than its timeout. Assume Bedrock can be slow or unavailable during the demo, and design so it doesn't matter.

### 4.11 Data and ingestion
- **The Wellness Calendar** is a public, read-only JSON API from the WordPress "The Events Calendar" plugin. No key.
  - **Pagination:** page through with `per_page` and `next_rest_url`.
  - **User-Agent:** send a descriptive, browser-like header; the default Python one gets 403.
  - **Cleanup:** titles contain HTML entities and descriptions contain HTML. `cost` is often blank, which means unknown, not free.
  - **Locations:** venues have addresses but no coordinates.
  - **Incremental sync:** use the `modified` field.
  - **Fallback:** an iCal feed exists (`?ical=1`).
  - **Size:** 58 upcoming events as of Oct 10.
  - **Politeness:** pull at most hourly and cache everything.
  - **Details:** see `kb/ingest.py` and the v1 doc.
- **ScarletWell resource list:** New Brunswick resources by dimension, parsed in the starter.
- **Newark and Camden are thin.** Today there are 2 real items each, plus 2 online services and 56 labelled sample events. Research about 30 real ones from Rutgers–Newark and Rutgers–Camden student affairs pages: counselling, health, food pantries, tutoring, recreation, career, commuter services, cultural and faith centres. Store the source URL and the date verified. Don't invent hours.
- **Geocoding:** Amazon Location Service, or OpenStreetMap's Nominatim with its rate limits. Cache per address.
- **The Arc and getINVOLVED are login-only.** Don't scrape them. If the organizers provide an export, add an importer.
- **Labelling:** every synthetic or sample record stays labelled end to end.

### 4.12 Personas and the demo flows the backend must make deterministic
| Persona | Situation | What the demo needs |
|---|---|---|
| **Andre** (main) | Newark junior, commuter, first-gen, works afternoons. Free Tue and Thu 12:20 to 14:30. Social 1.9, strongest spiritual 3.4 | Picks social, taps "don't know anyone" and "no time". Gets a structured rung-2 event in his Tuesday gap at the Paul Robeson Campus Center (a labelled sample event is fine). Plans it, invites a friend, gets a reminder, rates it 4. Credit and challenge progress show. Next week's pick is the next rung. A later take shows social 2.4 |
| **Priya** | New Brunswick sophomore on Busch, Calc II, sleep problems. Physical 2.0, intellectual 2.3 | The judge's own example: sleep is low because of coursework. Her pick is the **real** Busch Learning Center tutoring. This satisfies "a real, geolocated resource" in the brief |
| **Taylor** | Very low emotional (1.3) and several low areas | Care-first: the first card is a person, crisis lines visible, no event pushed |
| **Sofia** | Camden grad student, works full time, prefers Spanish. Financial 1.9 | Shows Camden's thin financial supply: falls back to real resources (food pantry, financial aid) and online. Spanish wording is a stretch |
| **Jordan** | New Brunswick first-year on Livingston, lonely, athletic | A rung 1 or 2 step and a residence-hall challenge |

Persona details are in `data/personas.json`. Add pinned demo events where you need determinism, labelled as samples, placed relative to the simulated clock.

---

## 5. API surface (contract to finalize and own)

Publish this as OpenAPI early. Names are suggestions; keep the shapes stable once the frontend starts. Every response that involves synthetic data says so.

| Area | Endpoint (suggested) | Purpose | Returns, in short |
|---|---|---|---|
| Session | demo session or persona select | Choose persona, set the simulated clock, reset state | Session token, current simulated time |
| Student | `GET /me/map` | Latest scores and trend | 8 dimensions with band, total, strengths, care-first flag, previous takes |
| Student | `POST /me/focus` | Chosen dimension, barrier chips, optional text | Updated profile, or the crisis response if the text triggered it |
| Student | `GET /me/next` | One pick plus two alternates | For each: item details, time, place, walking time, cost, rung, going count, structured reasons, why line |
| Student | `POST /me/next/{id}/decline` | Swap or "not now" | Next best |
| Student | `GET` and `DELETE /me/memory` | What Compass knows, and deleting it | Each item: what, where it came from, when, how it's used |
| Student | `GET /me/card` | Compact "your next step" for the MyRutgers card mock | Title, time, one line |
| Loop | `POST /commitments` | "I'm in" | Plan text, calendar file or link, reminder time, invite link |
| Loop | `GET` and `POST /invites/{token}` | Friend's public page and "I'll come too" | Event details only; nothing about the inviter's scores |
| Loop | `POST /followups/{id}` | Went, helped (1 to 5) | Progress delta, Arc credit status, challenge progress, next-rung suggestion |
| Social | `GET /pulse` | Campus challenges and wins | Challenge bars, approved wins |
| Social | `POST /wins` | Post a win | Accepted (pending moderation), rejected, or the private crisis response |
| Notify | push key and subscription endpoints | Web push setup | VAPID public key; store or delete a subscription |
| Staff | `GET /staff/funnel`, `/staff/gaps`, `/staff/weekly`, `/staff/dips`, `/staff/retakes` | Aggregates | Groups under 10 suppressed; synthetic flag |
| Demo | `POST /demo/skip-ahead`, `POST /demo/reset` | Control the story | What fired; new simulated time |
| Ops | `GET /health` | Liveness and readiness, including DB and Bedrock reachability | Status per dependency |
| P2 | Ask, staff ask, voice chat-completions | Stretch | Scoped, crisis-checked |

---

## 6. AWS: decisions are yours, within these constraints

- **Cheap and simple beats clever.** We have no hard budget, but keep it small and tag every resource (`project=compass`) so it can be torn down after judging.
- **Region:** pick one where the Claude models we need are enabled on Bedrock, likely us-east-1. Confirm model access first thing. Newer models may need an inference-profile ID rather than a base model ID.
- **Compute:**
  - **Options:** a container service with managed HTTPS (App Runner or ECS on Fargate behind a load balancer), or Lambda behind API Gateway. Check current availability and limits.
  - **Criteria:** stable HTTPS URL, no cold-start surprises during the demo, easy redeploys at 3 a.m.
  - **Plan for P2 voice:** it needs a streaming endpoint.
- **Database:** Postgres with pgvector (RDS PostgreSQL small instance, or Aurora Serverless v2 if you prefer). Encryption at rest is on by default. Keep the network access tight; managed connection secrets.
- **Scheduling:**
  - **Requirement:** reminders and follow-ups fire reliably, and skip-ahead fires them instantly.
  - **Options:** EventBridge Scheduler (one-time schedules), with a Lambda or HTTP target, reads well on the architecture slide. An in-process scheduler is fine for the demo if it's robust.
- **Bedrock:** Claude for wording, tagging, moderation and classification; Guardrails as in 4.9; optionally an embedding model.
- **Location:** Amazon Location Service for geocoding, if it's quick to set up.
- **Secrets:** Secrets Manager or SSM for the VAPID private key, the DB credentials, and an ElevenLabs key if P2 happens. Nothing in the repo.
- **Observability:** CloudWatch logs, structured, with request IDs. **No free text and no scores in logs.**
- **Email (optional weekly digest):** SES starts in sandbox mode, so only verified recipients receive mail. That's fine for a demo.
- **Infrastructure as code** (CDK, Terraform or SAM) if it doesn't slow you down. Otherwise, a scripted, documented setup. Whatever you choose, someone else must be able to redeploy from the README.
- **Frontend:** teammates will probably host on AWS Amplify Hosting. Coordinate CORS and the API URL with them.

---

## 7. Research and design: think hard here, then decide

**These are the problems where an hour of thinking beats an hour of typing.** We've deliberately not given you answers.

For each problem:
1. **Time-box the research** to roughly 30 to 60 minutes.
2. **Read primary sources:** repos, design docs, papers. Not blog summaries.
3. **Write a short decision** in the repo's decision log: what you chose, what you rejected, and why.
4. **Then build.**

**Prefer proven open-source building blocks with permissive licences** (MIT, Apache-2.0, BSD). Look carefully before pulling in anything AGPL. Borrow ideas freely; copy code only where the licence allows, with attribution.

Every answer must respect the constraints that are not up for debate:
- a deterministic, explainable core;
- the safety rules in 4.3 and 4.9;
- strict per-student isolation;
- the student can see and delete everything Compass knows about them;
- synthetic data stays labelled;
- the student flow works with Bedrock down;
- it ships by Sunday morning.

### 7.1 How should Compass remember a student?
A judge asked for Compass to "learn and build up a user profile over time". Done well, it's a differentiator. Done badly, it's a privacy story.

**Study how serious open-source agents handle long-term memory and user profiles, for example:**
- **Hermes Agent (Nous Research):** how it decides what's worth remembering about its user, how it keeps the profile small and accurate, how it stops memory drifting or bloating, and how the user can inspect it.
- **OpenClaw:** how it separates day-to-day logs from curated long-term memory, and what it does before a long conversation is compacted.
- **Letta (formerly MemGPT), mem0, Honcho:** memory blocks, background consolidation, add, update and delete semantics, user modelling. Check Honcho's licence.
- **Amazon Bedrock AgentCore Memory:** AWS's managed take, with extraction strategies, consolidation and per-user namespaces.

**Then answer, for our setting** (many students, a wellness-adjacent product, judged partly on privacy):
- What is worth remembering for engagement, such as preferences, constraints, schedule, what helped and social rung? What must never be stored?
- Who writes memory: rules driven by taps, a model reading free text, or both? Inline or in the background? How are stale or wrong facts corrected?
- How does memory feed the ranking in a way the reasons can show, like "because tutoring helped you last time"?
- Managed or self-hosted? How do you guarantee per-student isolation, real deletion, low cost and low latency?
- What does the student-facing "What Compass knows" screen list? Agree its shape with the frontend.

### 7.2 Does anything deserve an agent loop?
The core is deterministic on purpose. Some features might benefit from an agent with tools, or might be better as single, checked model calls:
- the Ask box;
- staff "ask the data";
- the ingestion and tagging pipeline;
- the voice endpoint.

**Look at:**
- **Strands Agents:** AWS's open-source agent SDK, Bedrock-native, with MCP support.
- **How Hermes Agent and OpenClaw structure their loops and tools.** OpenClaw builds on the Pi agent toolkit.
- **The Claude Agent SDK, LangGraph, and a plain Bedrock Converse tool loop.**

**Decide per feature**, judged on: safety and scope control, predictability, latency, observability, debuggability at 3 a.m., and how it reads on an AWS architecture slide. "No agent here" is a perfectly good answer.

### 7.3 A ranking that learns without losing explainability
Start with the rules in 4.4. Then think about learning from "did it help?" with sparse feedback and cold-start students.
- **Recommender approaches:** contextual bandits, Thompson sampling, simple Bayesian priors by cohort.
- **Mobile-health research** on just-in-time adaptive interventions (JITAI).

Whatever you add must be seedable for the demo, explainable in one sentence, and visible in the reasons.

### 7.4 Crisis detection that fails safe
Research how published systems and crisis-support organizations detect risk in short text: lexicons, classifiers, multilingual coverage, false-positive handling, escalation design.

Then decide:
- the phrase list;
- the classifier prompt and threshold;
- the failure behaviour.

Build the test set from what you learn. Bias toward catching every real case, and measure false alarms.

### 7.5 Nudges people don't hate
Look at what the evidence says about the timing, frequency and wording of pushes and emails: notification fatigue, fresh-start timing, personal versus generic reminders. In an Oregon State trial a third reminder email sometimes backfired. Turn what you learn into the scheduler's rules.

### 7.6 Retrieval for the knowledge base and the Ask box
The corpus is a few hundred items, so pick the simplest thing that's good. Options to weigh:
- hybrid keyword and vector search in Postgres with pgvector;
- multilingual embeddings on Bedrock, or an open-source embedding model;
- re-ranking.

### 7.7 Operational facts to confirm (quick)
- [ ] **Bedrock:** which Claude models and inference profiles are enabled in the account and region; current Guardrails features (denied topics, sensitive-information filters, prompt-attack protection, standalone checks); realistic latency for short calls.
- [ ] **Web push from a Python backend:** VAPID, payload limits, expired subscriptions (404 and 410 responses). iPhone constraints that affect the contract: push works only for web apps added to the Home Screen, and permission needs a user tap.
- [ ] **Wellness Calendar API edge cases:** pagination, recurring events, all-day events, virtual events.
- [ ] **Rutgers–Newark and Rutgers–Camden resources:** the ~30 items in 4.11.
- [ ] **Crisis lines per campus**, including after-hours options. Produce a verification sheet a human can call down.
- [ ] **Compute options** in the current AWS console. Pick within an hour.
- [ ] **ElevenLabs Agents "custom LLM"**, only if you reach P2: the OpenAI-compatible streaming format, how student identity reaches you, buffer words for slow turns.
- [ ] **How a real ScarletWell export is likely shaped.** Ask the humans; they may get a sample from the organizers.

---

## 8. Timeline and gates (Saturday evening to Sunday noon)

Post a three-line status to the team at each gate: done, blocked, contract changes.

| By | Gate |
|---|---|
| Sat 20:30 | Repo plus README. OpenAPI v0 with fixture responses for every endpoint. Frontend unblocked |
| Sat 22:00 | Postgres seeded (local and AWS). Map, focus and next live for all personas. Crisis check v1. Decision-log entries for memory (7.1) and the agent question (7.2) |
| Sun 00:00 | Deployed on AWS behind HTTPS. Commit, invite, follow-up and skip-ahead working. Push delivered to a test subscription. Arc mock |
| Sun 02:00 | Staff aggregates, dips and retakes. Going counts, challenges, wins moderation. Student memory working with a list-and-delete endpoint |
| Sun 06:00 | Live ingestion with AI tagging and geocoding. Newark and Camden research items in. Crisis test set at 100% |
| Sun 08:00 | All P0 and P1 green. Smoke test passes against production. "Why" lines pre-generated for the personas |
| Sun 09:00 to 10:00 | P2 only if everything above is green: Ask box, staff questions, voice, Spanish |
| Sun 10:30 | Feature freeze. Tag the release. Runbook ready: reset, skip-ahead, the fallback switch. Warm everything up |
| Sun 12:00 | Submission |

---

## 9. Definition of done (acceptance scenarios)

Run these against the deployed API, in a script, before the freeze:
1. **Andre end to end:**
   - set the clock; get the map with strengths first;
   - focus on social with two barriers; get the expected rung-2 pick in his Tuesday window, with reasons and a why line;
   - commit, with an invite link that works without an account;
   - skip ahead: the reminder fires inside the push budget and outside quiet hours;
   - skip ahead again: the follow-up arrives; answer went and helped 4;
   - Arc credit, challenge progress and the next-rung suggestion all show;
   - a later take shows social 2.4.
2. **Taylor:** care-first is on. The first card is human support for her campus. Nothing pushes an event.
3. **Priya:** the pick is the real Busch Learning Center, with a real address and source.
4. **Sofia:** a Camden pick falls back gracefully. Staff need-vs-supply shows Camden financial as the largest gap.
5. **Crisis:** every phrase in the test set returns the fixed crisis response through every free-text endpoint. No model output appears in that response, and no text is stored. False-alarm phrases pass through.
6. **Wins:** a normal post gets approved. A post with a name is held. A crisis post is never published and the poster gets the private response.
7. **Staff:** funnel totals match the dataset. Groups under 10 never appear. Dips line up with the midterm window and the finals dates.
8. **Resilience:**
   - With Bedrock blocked (simulate it), every student endpoint still answers within its latency budget using templates.
   - With the DB unreachable, fixture mode serves the demo.
   - Reset returns to the exact demo start state.
9. **Memory:** after Andre rates game lunch 4, something like "likes structured events" appears in what Compass knows, and the next pick's reasons cite it. Deleting it removes it everywhere, and the reasons stop citing it.
10. **Forget me:** deleting a student removes everything personal, memory included. Only anonymous safety counts remain.

Latency targets: student endpoints under 1.5 s at p95 with cached wording; staff endpoints under 1 s.

---

## 10. Working agreements

- **Small, frequent commits** with clear messages. Keep the README current: run locally, seed, reset, deploy, smoke test.
- **The contract is shared.** Additive changes are fine; tell the frontend in the same breath. Breaking changes need a heads-up and a reason.
- **Ask the humans** when a decision changes what judges see, what the frontend builds, or what we claim in the pitch. Otherwise decide, and note it in a decision log in the repo (one line each).
- **No real student data**, ever, in this hackathon. Everything synthetic stays labelled. No names, emails, NetIDs or phone numbers of students anywhere.
- **Don't scrape login-gated systems.** Respect the Wellness Calendar: hourly at most, identify yourself in the User-Agent.
- **Don't copy code from other teams' public repos.** At least one other team works on a similar idea; we read their public notes for positioning only.
- **If blocked for more than 30 minutes, take the simpler path and say so.**

---

## 11. Open questions (humans own these; defaults to use until answered)

| Question | Default until answered |
|---|---|
| Official inventory scoring, scale and cut-offs | 1 to 4 scale; low below 2.3, high from 3.2; all in config |
| Care-first thresholds | Emotional 1.6 or below, or low plus 3 other low areas |
| Exact submission time | Sunday 12:00 ET |
| Crisis lines and their exact wording | Use the list in `kb/items.json` only after a human verifies it; until then show it marked "verify" in dev only |
| Shape of ScarletWell's real export | Wide CSV per take; build a configurable mapping |
| Domain or URL for the demo | Whatever AWS gives you; a custom domain is optional |

---

## 12. What we need from you for the pitch

- An architecture diagram: data in → database → engine and safety → student app, staff view, The Arc. Name the AWS services.
- Five sentences on how it's built and why it's safe, written for non-engineers.
- Numbers you can stand behind: response times, test-set pass rate, how many real items per campus, how often the data refreshes.
- One honest line on what's mocked (The Arc, the synthetic data) and what it would take to make it real.

Build it like it'll be piloted in the spring, because that's the ask we're making.
