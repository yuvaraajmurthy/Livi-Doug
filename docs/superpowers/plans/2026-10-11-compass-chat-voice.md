# Compass v2 (chat, voice, calmer stage): implementation plan

**Goal:** Chat tab on a Strands agent with event buttons, event cards with map and reminders, mem0/Hermes/OpenClaw-
style memory, browser voice mode on Nova 2.5 Sonic, Campus tab removed, stage redesigned around one focal point.

**Spec:** `docs/superpowers/specs/2026-10-11-compass-chat-voice-design.md` (contracts in §3.6, §3.7, §4 are binding).

**Execution:** Codex CLI agents (`codex exec`, model gpt-6.1-sol, reasoning high, `--sandbox workspace-write` with
network) run tracks A, C, D in parallel on disjoint files, B after A. Claude does track E, integrates, reviews every
diff, runs the suites, deploys and runs Playwright on production.

## Global constraints (every track)

- Worktree root: `C:\Users\sibte\Desktop\Codeine\ruhack\compass-backend`. Python: `.venv\Scripts\python` (3.12,
  strands-agents[bidi] 1.59.0 installed). Web: `web/` (React 19, Vite 7, Tailwind 4, TanStack Query 5, motion 12,
  Phosphor icons; follow `web/src/ui/*` and tokens in `web/src/styles/tokens.css`; no new UI kit).
- Only edit the files your track owns (table in spec §7) plus the explicit shared edits listed in your track.
- Never run git commands that change state (commit, checkout, reset, stash, clean, rebase). Leave changes in the
  working tree; Claude reviews and commits.
- Never print or commit secrets. AWS credentials come from the environment; nothing reads `C:\Users\sibte\Downloads\env`.
- Unit/component tests must not call Bedrock or the network except the test Postgres (`TEST_DATABASE_URL` in `.env`,
  used through the existing `client`/`db` fixtures in `tests/conftest.py`). Use test doubles for models.
- Code style: match the surrounding code (comment density, naming). Python: type hints, small functions, psycopg 3
  dict rows, `app.db.conn()`. TypeScript: strict, no `any` in exported types.
- Safety rule: any user free text goes through `app.safety.lexicon.scan` (stage 1) before any model call.
- When done: write a short report to `.codex-out/<track>.md` (what changed, how to run tests, results, open issues).

## Track A: Chat backend (Codex)

Files: `app/chat/{__init__,catalog,prompt,tools,memory,agent,fallback,service,models}.py`, `app/routes/chat.py`,
`app/routes/items.py`, `db/migrations/005_chat.sql`, `tests/chat/test_*.py`. Shared edits: `app/main.py` (include
the two routers), `requirements.txt` (add `strands-agents[bidi]==1.59.0`), `contract/openapi.json` via
`python -m scripts.export_openapi`, `contract/CHANGELOG.md` (v1.3.0 entry).

1. Migration 005: `chat_messages(id bigserial pk, student_id text fk students on delete cascade, conversation_id text,
   role text check in ('user','assistant'), text text, blocks jsonb default '[]', source text, created_at timestamptz
   default now())` + index (student_id, conversation_id, id); full-text index on text. `student_memory`: add
   `superseded_by bigint`, `chat_message_id bigint`; widen kind CHECK with likes, dislikes, interest, goal.
   `DELETE /me` and reset must still work (cascade).
2. `catalog.build(conn, sctx, now) -> list[CatalogItem]` and `catalog.render(items) -> str` (spec §3.2 line format,
   ≤80 rows, events in the next 14 days on campus + online + always-open resources). Reuse `app.repo.kb.load_items`.
3. `prompt.build(conn, ctx, now, style="chat"|"voice") -> PromptBundle(system: str, catalog_ids: set[str])` with the
   seven sections of spec §3.2 and the size caps; voice style changes only the Style section.
4. `tools.make_tools(tc: ToolContext) -> list` where `ToolContext` holds conn factory, SessionCtx, now, catalog ids,
   language, and `emit: Callable[[dict], None]`. Tools exactly as spec §3.3; every emitted dict matches §3.6 payloads
   (`{"type": "events", "items": [...]}` etc.). `set_reminder` and `POST /items/{id}/remind` share one service
   function that creates a recommendation row if none is open, then calls the existing commit service.
5. `memory.remember(conn, student_id, kind, fact, chat_message_id) -> MemoryItem | Refused` (lexicon + simple
   health/medication regex refusal; key = kind + normalized lemma; ADD + supersede; cap 25) and
   `memory.flush(conn, student_id, conversation_id)` (Haiku JSON extraction of ≤3 facts; no-op when models are off).
   `/me/memory` must show chat facts with source label "You said in chat" and hide superseded ones.
6. `agent.run_turn(...)` builds a Strands `Agent(model=BedrockModel(...), system_prompt, tools, messages=history)` and
   streams via `stream_async`, translating events to the SSE events of §3.6 (`delta`, `status` on tool start with
   friendly text per tool). 8 s first-token timeout → `fallback.respond(...)` (Ask retrieval → `events` + template
   line, `source: "fallback"`). Stage-2 classifier runs in parallel (`app.safety.check`), crisis cancels the stream.
7. `routes/chat.py`: `POST /chat` (StreamingResponse, `text/event-stream`, no buffering headers), `GET /chat/history`,
   `POST /chat/new`. `routes/items.py`: `GET /items/{id}`, `POST /items/{id}/remind` (contract §3.7).
8. Tests (`tests/chat/`): catalog render format and caps; prompt contains catalog ids and frozen snapshot, under size
   caps; `show_events` drops unknown ids and emits; `remember` refuses crisis/health text, supersedes same key, caps
   at 25; crisis message → only a `crisis` SSE event, nothing stored; fallback path when the model raises; items
   detail shape; remind idempotent; history returns stored blocks. Use a scripted fake Strands model (implement the
   `strands.models.Model` interface or monkeypatch `agent._make_model`) to emit a tool call to `show_events` then
   text.
Done when: `.venv\Scripts\python -m pytest -q` is fully green (existing ~290 tests plus new ones).

## Track B: Voice backend (Codex, after A)

Files: `app/voice_ws/{__init__,session,io}.py`, `app/routes/voice_ws.py`, `tests/voice/test_*.py`. Shared edit:
`app/main.py` (include router).

1. `WS /voice/ws` per spec §4 protocol. Validate token from the first frame. Build prompt with `style="voice"` and the
   track-A tools, `emit` forwarding `{type:"ui", event}` frames.
2. `BidiAgent(model=BedrockNovaSonicModel(model_id="amazon.nova-2-5-sonic", region=settings.aws_region,
   voice="tiffany", config={"audio": {"input": {"sample_rate": 16000}, "output": {"sample_rate": 24000}}}),
   system_prompt, tools)`; `await agent.start()`; reader task: client audio frames → `agent.send(AudioDelta(...))`
   (check exact class/import in the installed `strands/bidi` source), text frames → text input; writer task:
   `async for event in agent.receive()` → audio (`bidi_audio_delta` base64 passthrough), transcripts (delta/final),
   `bidi_barge_in`, errors. Final user transcripts → lexicon; crisis → `crisis` frame + stop.
3. Session cap 8 min, ping every 20 s, clean shutdown on disconnect; no PyAudio import anywhere on the server.
4. Tests with a fake bidi model (implement the `BidiModel` protocol used by `BidiAgent`) covering: auth required;
   audio frames reach the model; transcript and audio frames reach the client; tool UI events forwarded; crisis
   transcript ends the session with a crisis frame.
Done when: full pytest green and `python -c "import app.main"` works without PyAudio installed.

## Track C: Web chat and event card (Codex)

Files: `web/src/features/chat/**` (except `types.ts`, which exists; extend only), `web/src/features/event/**`,
`web/tests/component/chat*.test.tsx`, `web/tests/component/event*.test.tsx`. Shared edits: `web/package.json`
(`maplibre-gl`), `web/src/i18n/en.ts` + `es.ts` (new keys only, both files, parity test must pass).

1. `chat/sse.ts`: POST-based SSE client over `fetch` + `ReadableStream` (EventSource can't POST): base URL and token
   from `web/src/api/transport.ts` (`apiBase()`, `session.token()`), parses `event:`/`data:` frames, reports the call to
   the inspector (`inspector.emit({type:"call", ...})`) with total ms, emits a `signal("chat:...")` where useful.
2. `chat/ChatPage.tsx` (export `ChatPage`) per spec §5.2: empty state with profile-based chips (use `useMap()`),
   thread, streaming text, status line, event buttons, memory chip with Undo (`api.deleteMemory`), plan chip, support
   card (reuse `features/today/SupportFirst`), crisis (reuse `features/safety/CrisisScreen`), composer, New chat,
   history load on mount (`GET /chat/history`). Mic button renders `<VoiceLauncher />` from
   `features/voice/VoiceLauncher` (exists as a stub, track D owns it).
3. `event/EventSheet.tsx` (export `EventSheet({ eventId, onClose })`, stub exists, replace it) per spec §5.3 using
   `ui/Sheet`; `event/EventMap.tsx` lazy-loads `maplibre-gl` with style `https://tiles.openfreemap.org/styles/positron`,
   one scarlet marker, interactive off until tapped, graceful fallback on error/offline; Remind me → `POST
   /items/{id}/remind` → add to the plans store (`features/plan/plans.ts` `plans.add`) and show "Reminder set".
4. `data-tour` ids: `chat-input`, `chat-send`, `chat-chip-<n>`, `chat-event-<n>` (n = 0..2 in the latest message),
   `event-remind`, `event-directions`, `voice-open`.
5. Tests (Vitest + Testing Library + MSW): SSE parser handles split frames; streaming text renders; event buttons open
   the sheet which fetches `/items/:id`; Remind me posts once; crisis event shows CrisisScreen and the typed text is
   not echoed; memory chip Undo calls DELETE once.
Done when: `npx vitest run` and `npx tsc -b` pass in `web/`.

## Track D: Web voice mode (Codex)

Files: `web/src/features/voice/**` (replace the `VoiceLauncher` stub), `web/public/pcm-worklet.js`,
`web/tests/component/voice*.test.tsx`.

1. `voice/protocol.ts` (frames from spec §4), `voice/audio.ts` (mic capture through an AudioWorklet in
   `public/pcm-worklet.js`: Float32 → 16 kHz PCM16 → base64 ~40 ms chunks; playback queue at 24 kHz with gapless
   scheduling; `stop()` clears the queue for barge-in; input/output level meters for the orb).
2. `voice/VoiceSession.ts`: WS client (`wss://` derived from `apiBase()`), start frame with token, reconnect off,
   state machine idle → connecting → listening ↔ thinking ↔ speaking → ended/error.
3. `voice/VoiceOverlay.tsx` per spec §5.4 (orb, captions, event cards via `EventChip` buttons that open
   `EventSheet` from `features/event/EventSheet`, End, Mute, Type instead, permission-denied state, reduced motion).
   `voice/VoiceLauncher.tsx` = round mic button (`data-tour="voice-open"`, aria-label "Talk to Compass") that opens the
   overlay.
4. Tests: protocol encode/decode; state machine transitions on frames; overlay renders captions and event chips;
   barge_in clears playback; crisis frame shows CrisisScreen. Mock `WebSocket`, `AudioContext`, `getUserMedia`.
Done when: `npx vitest run` and `npx tsc -b` pass.

## Track E: Claude

1. Before launching agents: create `web/src/features/chat/types.ts` (contract types), stubs `features/voice/
   VoiceLauncher.tsx`, `features/event/EventSheet.tsx`; `.codex-out/` (gitignored).
2. Remove Campus: tab bar Today · Chat · Map · You; delete `features/campus` and `features/ask`; Today drops
   `AskLauncher`; story safety step moves to Chat; tours drop Campus.
3. Stage redesign per spec §6: `demo/present/*` rewritten (one focal point, show-then-tell sequencing, evidence
   styles, presenter window `/present/notes` via `BroadcastChannel`, In-numbers slide, simplified close). Story v2
   claims; new Chat chapter (after the retake).
4. Chat tour; e2e specs: chat on production (ask → buttons → card with map → remind), stage v2, tours.
5. Integrate tracks: wire `/chat` route; review diffs; full suites; deploy backend (`scripts.deploy --mode live`,
   then `--task migrate`), web (`--web`); smoke; Playwright on production; screenshots reviewed light/dark.
6. Re-record the offline replay including the chat chapter.

## Order

E1 → launch A, C, D in parallel → E2, E3 while they run → review A → launch B → review C, D → integrate (E5) →
review B → E4, E6 → final review → deploy.
