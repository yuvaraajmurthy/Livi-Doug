# Compass v2: Chat, voice, and a calmer stage

Date: 2026-10-11 · Status: approved direction from the user, plan follows in `docs/superpowers/plans/2026-10-11-compass-chat-voice.md`
Builds on: `2026-10-10-compass-web-design.md` (web app) and `2026-10-10-compass-backend-design.md` (API).

## 1. What changes and why

User direction (verbatim intent): remove the Campus tab; make the stage presentation far less cluttered so it guides
the eye; add a dynamic **Chat** tab built on the **Strands Agents SDK** whose system prompt carries every event
(title, place, time); it recommends events as **buttons**, and a tapped button opens a **card** with full details from
an API call, a **map**, **set reminder** and more; an agent loop with **memory** inspired by Hermes, OpenClaw and mem0;
and a **voice mode** built from the teammate's `voice_bot.py` (Strands `BidiAgent` + Nova Sonic).

Success:
1. A judge can type or say "anything social with free food this week?" and get two or three tappable events in under
   ~3 s, open one, see where it is on a map, and set a reminder in one tap.
2. The assistant remembers what the student tells it ("I play basketball", "Fridays after 3 are free"), shows that it
   remembered, uses it next time, and the student can see and delete it in You.
3. Voice mode works in a desktop/phone browser: talk, hear Compass answer, see the same event cards appear.
4. Every free-text path still goes through the code-first crisis check before any model.
5. The stage shows one thing at a time: the phone acts, then one short claim and one piece of evidence.

## 2. Research that shaped the design

| Source | Idea taken | How Compass uses it |
|---|---|---|
| Hermes Agent (Nous Research) | Small bounded memory files (MEMORY.md ~2.2k chars, USER.md ~1.4k) injected into the system prompt as a **frozen snapshot** at session start; full-text search over past sessions for older recall | A bounded **profile snapshot** (scores summary, focus, barriers, free windows, top memory facts) frozen into the prompt per conversation; past chats searchable through a tool |
| OpenClaw | Markdown memory as the durable record; agent tools `memory_search`/`memory_get`; **pre-compaction memory flush** (a silent turn asks the model to write durable notes before context is trimmed) | Agent tools `remember` / `forget` / `recall`; a **flush** after every 6 student turns (or on "new chat") extracts durable facts before older turns are dropped from the window |
| mem0 | Extract facts, then reconcile (ADD/UPDATE/DELETE/NOOP); the newer release moved to **ADD-only** because reconciliation was slow and destroyed context | **Add + supersede**: a new fact with the same key supersedes the old (old row kept, marked superseded) rather than being rewritten; no extra reconciliation call on the hot path |
| Compass backend principles | Code chooses, AI words; crisis check before any model; memory is inspectable | Unchanged. The chat model may only show events by id from the catalog; tools validate everything |

Sources: mem0 docs and papers (docs.mem0.ai, arXiv 2606.15903), Hermes write-ups (firecrawl.dev/blog/hermes-agent,
mranand.substack.com), OpenClaw memory docs (docs.openclaw.ai/concepts/memory), Strands SDK source 1.59.0
(`strands.bidi`, `strands.memory`), Codex non-interactive docs (developers.openai.com/codex/noninteractive).

## 3. Chat: the agent

### 3.1 Runtime

- Strands `Agent` (strands-agents 1.59.0) in the FastAPI backend, model `BedrockModel` = Claude Haiku 4.5
  (`us.anthropic.claude-haiku-4-5-20251001-v1:0`, us-west-2), streaming, guardrail `GUARDRAIL_ID`/`GUARDRAIL_VERSION`
  from settings, temperature 0.3, max tokens 600.
- One agent instance per request (stateless server); conversation context rebuilt from `chat_messages` (last 12
  turns, text only) so ECS restarts lose nothing.
- Fallback (Bedrock down, `force_templates`, or 8 s timeout): a deterministic responder uses the existing Ask hybrid
  retrieval to pick up to 3 catalog events and replies with a template sentence + the same `events` UI block. The chat
  never dead-ends on stage.

### 3.2 System prompt (built per conversation, cached for its life)

Sections, in order (each bounded):
1. **Role**: "You are Compass, a Rutgers wellness companion for one student. You help them find one doable thing this
   week from real Rutgers events and services, plan it, and follow through. You are not a therapist; you never
   diagnose, give medical or medication advice, or discuss self-harm methods."
2. **Style**: 1–3 short sentences; warm, specific, plain words; at most one question; never markdown lists of events
   (events are shown as buttons by a tool); Spanish if the student's language is `es`.
3. **Tool rules**: to suggest events ALWAYS call `show_events` with 1–3 ids from the catalog, then write one short
   line about why; never invent events, times or places; only call `set_reminder` when the student clearly says yes;
   call `remember` when the student states a lasting preference, constraint or interest; call `show_support` when the
   student sounds overwhelmed or asks for someone to talk to.
4. **Now**: simulated current time from the demo clock ("It is Monday Oct 12, 9:00 AM").
5. **Profile snapshot** (frozen, ≤1,500 chars): name, campus, level, housing, language; strengths and growth areas
   from the latest inventory (labels and bands, not raw scores); focus and barriers; free windows.
6. **Memory snapshot** (frozen, ≤2,000 chars): up to 15 active facts from `student_memory`, newest first, each
   `- [m:12] You enjoyed game-based events (from a rating)`.
7. **Event catalog**: every active item on the student's campus + online in the next 14 days (plus always-open
   resources), max 80 rows, one line each:
   `pin-andre-lunch-2026-10-13 | Commuter lunch and board games (sample) | Tue Oct 13 12:30–1:30 PM | Paul Robeson Campus Center | free | social, financial`.

### 3.3 Tools (Strands `@tool`, bound to the request's student and an `emit` callback)

| Tool | Args | Does | UI event emitted |
|---|---|---|---|
| `show_events` | `event_ids: list[str]` (1–3), `why: str` | Validates ids against the catalog (unknown ids dropped); records a recommendation row per item (for stats and reminders) | `events` |
| `get_event` | `event_id` | Full details for answering questions | none |
| `search_events` | `query` | Hybrid search (existing `app.ask.retrieval`) beyond the catalog window; returns ids + titles | none |
| `set_reminder` | `event_id` | Creates the commitment (plan text, reminder, follow-up) through the existing loop service | `plan` |
| `remember` | `fact`, `kind` ∈ likes, dislikes, time_works, constraint, interest, goal | Lexicon-checked (crisis/health terms refused), stored as `your_words`; same normalized key supersedes the older fact | `memory` |
| `forget` | `memory_id` | Deletes a student-visible fact | `memory_removed` |
| `recall` | `query` | Searches the student's memory facts and past chat turns (Postgres full-text) | none |
| `show_support` | none | Care-first support options for the campus | `support` |

### 3.4 Memory model

- Table `student_memory` (exists) gets columns: `superseded_by bigint null`, `chat_message_id bigint null`; new kinds
  `likes`, `dislikes`, `interest`, `goal` added to the CHECK. Source type `your_words` already exists. Active facts =
  `superseded_by IS NULL`. Cap 25 active (oldest `your_words` dropped first). All facts appear in You → What Compass
  knows, with source "You said in chat · Oct 12", and are deletable.
- **Flush** (OpenClaw-style, async, never blocks a reply): after every 6th student turn and on "New chat", one Haiku
  call reads the turns since the last flush and returns ≤3 durable facts as JSON (`kind`, `fact`); each goes through
  `remember` validation (ADD + supersede). Skipped when models are off.
- **Never stored**: crisis-flagged text, health/medication/diagnosis statements, other people's details. Chat messages
  flagged crisis are not stored at all.

### 3.5 Safety on every chat turn

1. Stage-1 lexicon `scan()` on the message. Crisis → `crisis` event (fixed card from `crisis_lines`), safety event
   recorded, text not stored, no model call.
2. Agent starts streaming immediately; stage-2 classifier runs in parallel. If it returns crisis before the turn ends,
   the stream is cut and a `crisis` event is sent.
3. Bedrock guardrail on the model (denied topics: diagnosis, medication, self-harm methods).
4. Concern-level text: the system prompt directs `show_support`.

### 3.6 Chat API (contract)

`POST /chat` (student token) body `{ "message": str (1–500), "conversation_id": str | null }` →
`text/event-stream`. Each SSE frame is `event: <type>` + `data: <json>`:

| event | data |
|---|---|
| `meta` | `{conversation_id, now}` |
| `status` | `{text}` e.g. "Checking this week's events…" (tool started) |
| `delta` | `{text}` streamed assistant text |
| `events` | `{items: EventChip[]}` where `EventChip = {id, title, when_label, venue, cost_label, synthetic, kind}` |
| `plan` | `CommitResponse` (existing schema) |
| `memory` | `{id, statement, kind}` |
| `memory_removed` | `{id}` |
| `support` | `SupportCard` (existing schema) |
| `crisis` | `CrisisResponse` (existing schema) |
| `done` | `{message_id, source: "ai" | "fallback"}` |
| `error` | `{message}` |

`GET /chat/history?conversation_id=` → `{conversation_id, messages: [{id, role, text, blocks: UIEvent[], at}]}`
(latest conversation when omitted). `POST /chat/new` → `{conversation_id}` (runs the flush for the old one).

### 3.7 Event detail API (contract)

`GET /items/{id}` (student token) → `ItemDetail`:
`{id, kind, title, summary, dimensions, synthetic, starts_at, ends_at, when_label, venue, address, lat, lon, campus,
cost, cost_label, url, phone, hours_text, walk_min, going: GoingCount, source: SourceRef, directions_url, ics_url|null}`
(`directions_url` = Google Maps search/directions link; `ics_url` only for timed events).

`POST /items/{id}/remind` (student token) → `CommitResponse` (creates the recommendation row if needed, then the
commitment). Idempotent per student+item while planned.

## 4. Voice

- `WS /voice/ws`. First client frame `{type:"start", token, conversation_id?}`; server validates the token.
- Strands `BidiAgent` with `BedrockNovaSonicModel(model_id="amazon.nova-2-5-sonic", region="us-west-2",
  voice="tiffany", audio input 16 kHz / output 24 kHz)`. Same system prompt builder in `voice` style (spoken, short,
  no lists, read times naturally), same tools; tool UI events go to the browser as `{type:"ui", event}` so cards appear
  while Compass speaks.
- Server loop uses `agent.start()`, `agent.send(AudioDelta(format="pcm", source={"bytes": pcm}))`, and
  `async for e in agent.receive()` (no PyAudio on the server).
- Client → server: `{type:"audio", data:<base64 pcm16 mono 16 kHz>}` (~40 ms chunks), `{type:"text", text}`,
  `{type:"stop"}`. Server → client: `{type:"ready"}`, `{type:"audio", data:<base64 pcm16 24 kHz>}`,
  `{type:"transcript", role:"user"|"assistant", text, final}`, `{type:"barge_in"}`, `{type:"ui", event:{type, ...}}`
  (same payloads as chat SSE), `{type:"crisis", ...CrisisResponse}`, `{type:"error", message}`, `{type:"end"}`.
- Safety: every final user transcript goes through the lexicon; crisis → `crisis` frame, session ends. Session cap 8
  minutes; server pings every 20 s (ALB idle timeout).
- Browser: `getUserMedia` (echo cancellation, noise suppression on) → AudioWorklet resamples to 16 kHz PCM16 → WS.
  Playback: queue of 24 kHz PCM16 buffers through one `AudioContext`; `barge_in` stops and clears the queue.
- Fallback when Nova Sonic or mic is unavailable: voice button offers "Type instead".
- Same AWS account as the teammate's bot. Nova 2.5 Sonic is available in us-west-2 (checked). The teammate's
  knowledge base (us-east-1) is an optional later tool; their e-mail Lambda is out of scope.

## 5. Web app changes

### 5.1 Navigation
Tabs become **Today · Chat · Map · You** (Campus removed; its cup progress still appears in the follow-up result).
The Ask sheet and launcher are removed; Chat replaces them.

### 5.2 Chat screen `/chat`
- **Empty state**: serif greeting "Hi Andre." + one line "Ask about anything on at Rutgers this week." + 4 suggestion
  chips built from the profile ("Something social in my Tuesday gap", "Free food this week", "Quiet place to study
  tonight", "What can I do about money stress?").
- **Thread**: student messages right-aligned ink bubbles; Compass messages left, no bubble, plain 17 px text, streaming
  with a soft caret; a status line with a spinner while a tool runs ("Checking this week's events…").
- **Event buttons** under the Compass message: full-width stacked buttons (title, then "Tue 12:30 · Robeson ·
  Free"), sample badge, chevron. Max 3. Tapping opens the event card.
- **Memory chip** inline: "Saved to memory: You play basketball · Undo".
- **Plan chip**: "Reminder set · Tue 12:15 PM · View plan".
- **Composer** pinned above the tab bar: auto-growing textarea, send button, mic button (voice mode), "New chat" in
  the header menu.
- Crisis → the existing CrisisScreen.

### 5.3 Event card (sheet)
Opened from any event button (chat or voice). Fetches `GET /items/{id}`; skeleton until loaded.
1. Title, sample badge, dimension tags.
2. **Map**: MapLibre GL + OpenFreeMap "positron" style, 160 px tall, rounded, single scarlet marker, non-interactive
   until tapped; online items show an "Online" panel instead; tiles failing → address text only. Lazy-loaded chunk.
3. Facts: when (+ "fits your Tuesday gap" if the window matches), where + walk minutes, cost, going.
4. Actions: primary **Remind me** (`POST /items/{id}/remind` → "Reminder set for 12:15 PM" + View plan);
   secondary row: **Directions** (directions_url), **Add to calendar**, **Invite a friend** (after a plan exists),
   **Open source page** (url).
5. Summary text and source line ("Rutgers Wellness Calendar · verified Oct 10").

### 5.4 Voice mode overlay
Full-screen, calm: large breathing orb (scale follows input/output level; reduced-motion → static ring with text
state), state label (Listening / Thinking / Speaking), live captions (last 2 lines), event cards slide up when the
agent shows events (tap → event card), End button (scarlet), Mute toggle, "Type instead" link. Permission denied →
plain explanation + "Type instead".

## 6. The stage, redesigned (UI/UX)

Problems in v1: chapter dots, timer, badges, claim, a dense proof card, presenter notes, request log and a key-hint
footer all on screen at once; the eye has no entry point and the audience reads instead of watching.

Principles: **one focal point per step**; **show, then tell** (the phone acts first, the claim follows); **one idea
per claim (≤ 9 words)**; **one piece of evidence** (a number or a three-word chip, never a paragraph); presenter
aids leave the audience screen.

Layout (1280×720 and up): phone larger and vertically centered (≈ 88% of height) at left-of-center; to its right a
single column: small step kicker (e.g. "One step"), the claim (serif, 52–64 px), one evidence element. A 3 px progress
line at the very top replaces chapter dots. No footer; controls appear only on mouse move and fade after 2 s.

Sequencing per step: on arrival the claim area is empty and the phone acts (with the tap ripple); when the step's
action settles the claim fades up (240 ms), then the evidence (+150 ms). Pressing → again before settling skips ahead
cleanly.

Evidence styles (only one per step): **Number** ("212 ms", "1.9 → 2.4", "20.5 per resource"), **Chip row** (≤3
short chips: "Code check · 0.2 ms" → "AI: not called"), **Quote** (the plan sentence), **Bars** (five tiny weight bars,
no labels beyond names).

Presenter aids move to a **presenter window** (`/present/notes`, opened with N): next step, speaker note, timer,
live request log, mode toggles (AI off, offline), synced with the stage through `BroadcastChannel`. The audience
window shows only mode badges when something is not live (Offline replay / AI off).

Slides: cold open = two lines + the plain results illustration. A new **"In numbers"** slide carries the four
numbers. Close = headline + pilot metric + QR, nothing else.

Main story v2 (claims ≤ 9 words): Cold open → Strengths first → He picks one area → Two taps: what's in the way →
One step that fits his week (212 ms) → Code ranks. AI only words it (bars) → A plan in his own words (quote) →
Tuesday 12:15: a nudge → Did it help? Two taps → It learns. He decides what stays (chips) → Next week, one step bolder
→ Social 1.9 → 2.4 (number) → **Or just ask** (chat: "anything with free food Thursday?" → buttons → card with map →
Remind me) → Ask why. Fix the cause (Priya) → Sometimes a person comes first (Taylor) → Crisis words never reach AI
(typed in Chat) → Staff see where to act → Never who → In numbers → Ready for a spring pilot.

Tours: a new **Chat** tour (ask → buttons → card → remind me → memory chip); Campus references removed.

## 7. Delivery

Implementation is split across Codex agents (gpt-6.1-sol, reasoning high) working on disjoint file sets against the
contracts above, with Claude integrating, reviewing, testing end to end on production and deploying:

| Track | Owner | Files |
|---|---|---|
| A. Chat backend (agent, tools, memory, SSE, items API, migration 005, tests) | Codex | `app/chat/**`, `app/routes/chat.py`, `app/routes/items.py`, `db/migrations/005_chat.sql`, `tests/chat/**` |
| B. Voice backend (WS, BidiAgent, IO, tests) | Codex, after A | `app/voice_ws/**`, `app/routes/voice_ws.py`, `tests/voice/**` |
| C. Web chat + event card + map | Codex | `web/src/features/chat/**`, `web/src/features/event/**`, `web/tests/component/chat*.test.tsx` |
| D. Web voice mode | Codex | `web/src/features/voice/**`, `web/public/pcm-worklet.js`, `web/tests/component/voice*.test.tsx` |
| E. Stage redesign, tabs, story/tours, integration, deploy, e2e | Claude | `web/src/demo/**`, `web/src/app/**`, `web/src/ui/TabBar.tsx`, infra, docs |

Risks: Codex agents colliding (mitigated by disjoint ownership, no git commands for agents, stubs created first);
Strands API drift (pinned 1.59.0, agents read installed source); Nova Sonic latency or mic permissions on stage
(voice is a Q&A feature, not in the main story); SSE buffering through CloudFront (verified with the existing
`/v1/chat/completions` streaming path); token cost (Haiku, 600 max tokens, catalog ≤ 80 rows).
