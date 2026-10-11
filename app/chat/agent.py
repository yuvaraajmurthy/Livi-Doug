"""One chat turn (spec §3.1, §3.5, §3.6) as an async stream of (event, data) pairs for SSE.

Order of operations: stage-1 lexicon (crisis never reaches a model and is never stored) → persist the user turn →
frozen prompt (profile + memory snapshot + catalog) → Strands agent streaming, with the stage-2 classifier running in
parallel and able to cancel → tool UI events and text deltas → persist the assistant turn → memory flush every 6th
student turn (background). Models off, failing or slow → deterministic fallback with the same UI blocks."""
import asyncio
import logging
import threading
from collections.abc import AsyncIterator
from typing import Any

from app import clock
from app.auth import SessionCtx
from app.chat import fallback, memory, prompt, store
from app.chat.tools import ToolContext, make_tools, status_text
from app.db import conn
from app.safety import crisis
from app.safety.check import check_text, record_event
from app.safety.lexicon import scan
from config.settings import get_settings

log = logging.getLogger("compass.chat")
FIRST_OUTPUT_TIMEOUT_S = 10.0
TURN_TIMEOUT_S = 45.0


def models_available() -> bool:
    from app.llm import bedrock
    return bedrock.enabled() and not get_settings().force_templates


def make_model(style: str = "chat"):
    from botocore.config import Config
    from strands.models.bedrock import BedrockModel
    from strands.models.model import CacheConfig
    s = get_settings()
    # Runs in assistant_region (us-east-1) beside the guardrail, KB and email Lambda. No native guardrail attachment:
    # as in voice_bot.py, the guardrail is enforced through the system prompt (assist_aws.guardrail_rules).
    kw: dict[str, Any] = dict(model_id=s.model_fast, region_name=s.assistant_region, temperature=0.3, max_tokens=600,
                              cache_config=CacheConfig(strategy="auto"),
                              streaming=True, boto_client_config=Config(read_timeout=30, connect_timeout=5, retries={"max_attempts": 2}))
    return BedrockModel(**kw)


def sse_pair(ui: dict) -> tuple[str, dict]:
    """UIEvent (as stored in blocks) → (SSE event name, data)."""
    t = ui["type"]
    if t == "events":
        return "events", {"items": ui["items"]}
    if t == "plan":
        return "plan", ui["plan"]
    if t == "support":
        return "support", ui["card"]
    if t == "crisis":
        return "crisis", ui["crisis"]
    return t, {k: v for k, v in ui.items() if k != "type"}


def _prepare(ctx: SessionCtx, message: str, conversation_id: str | None) -> dict:
    with conn() as c:
        now = clock.now(c, ctx.sid)
        conv = conversation_id or store.latest_conversation(c, ctx.student_id) or store.new_conversation_id()
        hit = scan(message)
        if hit.label == "crisis":
            from app.safety.check import SafetyVerdict
            record_event(c, ctx.student_id, "ask_box", SafetyVerdict("crisis", "lexicon", hit.codes), "crisis_card")
            s = c.execute("SELECT campus FROM students WHERE id = %s", (ctx.student_id,)).fetchone()
            p = c.execute("SELECT language FROM profiles WHERE student_id = %s", (ctx.student_id,)).fetchone() or {}
            card = crisis.crisis_response(c, s["campus"], p.get("language") or "en", now)
            return {"now": now, "conv": conv, "crisis": card.model_dump(mode="json")}
        rows = store.messages(c, ctx.student_id, conv)
        user_id = store.add(c, ctx.student_id, conv, "user", message, at=now)
        bundle = prompt.build(c, ctx, now)
        return {"now": now, "conv": conv, "crisis": None, "history": store.agent_history(rows), "bundle": bundle,
                "user_id": user_id}


def _finish(ctx: SessionCtx, conv: str, text: str, blocks: list, source: str, now) -> int:
    with conn() as c:
        mid = store.add(c, ctx.student_id, conv, "assistant", text, blocks, source, at=now)
        turns = store.user_turns(c, ctx.student_id, conv)
    if turns and turns % memory.FLUSH_EVERY == 0 and models_available():
        threading.Thread(target=_flush, args=(ctx.student_id, conv), daemon=True).start()
    return mid


def _flush(student_id: str, conv: str) -> None:
    try:
        with conn() as c:
            memory.flush(c, student_id, conv)
    except Exception:  # never let a background flush hurt anything
        log.exception("memory flush failed")


def _fallback(ctx: SessionCtx, message: str, prep: dict) -> tuple[str, list[dict]]:
    with conn() as c:
        text, chips = fallback.respond(c, message, prep["bundle"], prep["now"])
    return text, ([{"type": "events", "items": chips}] if chips else [])


async def run_turn(ctx: SessionCtx, message: str, conversation_id: str | None = None) -> AsyncIterator[tuple[str, dict]]:
    prep = await asyncio.to_thread(_prepare, ctx, message, conversation_id)
    now = prep["now"]
    yield "meta", {"conversation_id": prep["conv"], "now": now.isoformat()}
    if prep["crisis"]:
        yield "crisis", prep["crisis"]
        yield "done", {"message_id": 0, "source": "rule"}
        return

    bundle = prep["bundle"]
    if not models_available():
        text, blocks = await asyncio.to_thread(_fallback, ctx, message, prep)
        for b in blocks:
            yield sse_pair(b)
        yield "delta", {"text": text}
        mid = await asyncio.to_thread(_finish, ctx, prep["conv"], text, blocks, "fallback", now)
        yield "done", {"message_id": mid, "source": "fallback"}
        return

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    cancel = threading.Event()
    blocks: list[dict] = []

    def emit(ui: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, ("ui", ui))

    tc = ToolContext(ctx=ctx, bundle=bundle, now=now, emit=emit, user_message_id=prep["user_id"])

    async def produce():
        from strands import Agent
        try:
            agent = Agent(model=make_model("chat"), system_prompt=bundle.system, tools=make_tools(tc),
                          messages=prep["history"], callback_handler=None)
            async for ev in agent.stream_async(message, cancel_signal=cancel):
                await queue.put(("agent", ev))
        except Exception as exc:  # model/network failure → fallback (handled by the consumer)
            log.warning("chat agent failed", extra={"err": type(exc).__name__})
            await queue.put(("fail", exc))
        finally:
            await queue.put(("end", None))

    async def stage2():
        verdict = await asyncio.to_thread(check_text, message)
        if verdict.label == "crisis":
            cancel.set()
            await queue.put(("crisis", verdict))

    producer = asyncio.create_task(produce())
    checker = asyncio.create_task(stage2())
    text, seen_tools, got_output, failed = "", set(), False, False
    pending = ""  # text of the current model message, held until we know it isn't narration before a tool call

    def flush():
        nonlocal text, pending
        out = pending.strip()
        pending = ""
        if not out:
            return None
        out = (" " if text else "") + out
        text += out
        return out

    try:
        while True:
            try:
                kind, payload = await asyncio.wait_for(queue.get(), FIRST_OUTPUT_TIMEOUT_S if not got_output else TURN_TIMEOUT_S)
            except asyncio.TimeoutError:
                cancel.set()
                failed = True
                break
            if kind == "end":
                if (out := flush()):
                    yield "delta", {"text": out}
                break
            if kind == "fail":
                failed = True
                continue
            if kind == "crisis":
                with conn() as c:
                    from app.safety.check import SafetyVerdict
                    record_event(c, ctx.student_id, "ask_box", payload, "crisis_card")
                    c.execute("DELETE FROM chat_messages WHERE id = %s", (prep["user_id"],))
                    card = crisis.crisis_response(c, bundle.campus, bundle.language, now)
                yield "crisis", card.model_dump(mode="json")
                yield "done", {"message_id": 0, "source": "rule"}
                return
            if kind == "ui":
                got_output = True
                blocks.append(payload)
                yield sse_pair(payload)
                continue
            ev = payload
            if "data" in ev and isinstance(ev["data"], str):
                got_output = True
                pending += ev["data"]
            elif "messageStop" in (ev.get("event") or {}):
                # a message that ends in a tool call was narration ("Let me search…"); the status line covers it
                if ev["event"]["messageStop"].get("stopReason") == "tool_use":
                    pending = ""
                elif (out := flush()):
                    yield "delta", {"text": out}
            elif ev.get("type") == "tool_use_stream":
                pending = ""
                tu = ev.get("current_tool_use") or {}
                tid = tu.get("toolUseId")
                if tid and tid not in seen_tools:
                    seen_tools.add(tid)
                    got_output = True
                    yield "status", {"text": status_text(tu.get("name", ""), bundle.language)}
    finally:
        checker.cancel()
        if not producer.done():
            cancel.set()

    if failed and not text and not blocks:
        text, blocks = await asyncio.to_thread(_fallback, ctx, message, prep)
        for b in blocks:
            yield sse_pair(b)
        yield "delta", {"text": text}
        mid = await asyncio.to_thread(_finish, ctx, prep["conv"], text, blocks, "fallback", now)
        yield "done", {"message_id": mid, "source": "fallback"}
        return
    mid = await asyncio.to_thread(_finish, ctx, prep["conv"], text.strip(), blocks, "ai", now)
    yield "done", {"message_id": mid, "source": "ai"}
