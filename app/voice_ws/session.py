"""One voice session: browser audio in, Nova Sonic audio + transcripts + UI cards out.

Same prompt builder (spoken style) and the same tools as chat, so events the agent shows appear as cards on the
student's screen while it talks. Every final user transcript goes through the code lexicon; a crisis ends the session
with the fixed crisis card. Final transcripts are kept as chat turns (not crisis ones), so voice and chat share one
conversation and one memory."""
import asyncio
import base64
import logging
import time
from typing import Any

from starlette.websockets import WebSocket, WebSocketDisconnect

from app import clock
from app.auth import SessionCtx
from app.chat import prompt, store
from app.chat.tools import ToolContext, make_tools
from app.db import conn
from app.safety import crisis
from app.safety.check import SafetyVerdict, record_event
from app.safety.lexicon import scan
from config.settings import get_settings

log = logging.getLogger("compass.voice")
SESSION_CAP_S = 8 * 60
PING_EVERY_S = 20


def make_agent(system_prompt: str, tools: list) -> Any:
    """The real bidirectional agent. Tests replace this with a fake that has start/send/receive/stop."""
    from strands.bidi.agent import BidiAgent
    from strands.bidi.models import BedrockNovaSonicModel
    s = get_settings()
    # amazon.nova-2-5-sonic in assistant_region (us-east-1), as in voice_bot.py; guardrail rules are in system_prompt
    model = BedrockNovaSonicModel(model_id=s.model_voice, region=s.assistant_region, voice=s.voice_name,
                                  audio={"input": {"sample_rate": 16000}, "output": {"sample_rate": 24000}})
    return BidiAgent(model=model, system_prompt=system_prompt, tools=tools)


def audio_input(pcm: bytes) -> Any:
    from strands.bidi.types.media import AudioDelta
    return AudioDelta(format="pcm", source={"bytes": pcm})


def _prepare(ctx: SessionCtx, conversation_id: str | None) -> dict:
    with conn() as c:
        now = clock.now(c, ctx.sid)
        conv = store.start(c, ctx.student_id, conversation_id or store.latest_conversation(c, ctx.student_id))
        bundle = prompt.build(c, ctx, now, style="voice")
        return {"now": now, "conv": conv, "bundle": bundle}


def _save(ctx: SessionCtx, conv: str, role: str, text: str, blocks: list, now) -> None:
    if not text.strip():
        return
    with conn() as c:
        store.add(c, ctx.student_id, conv, role, text.strip(), blocks, "voice", at=now)


def _crisis_card(ctx: SessionCtx, bundle, now, codes) -> dict:
    with conn() as c:
        record_event(c, ctx.student_id, "voice", SafetyVerdict("crisis", "lexicon", codes), "crisis_card")
        return crisis.crisis_response(c, bundle.campus, bundle.language, now).model_dump(mode="json")


async def run(ws: WebSocket, ctx: SessionCtx, conversation_id: str | None) -> None:
    prep = await asyncio.to_thread(_prepare, ctx, conversation_id)
    bundle, now, conv = prep["bundle"], prep["now"], prep["conv"]
    loop = asyncio.get_running_loop()
    out: asyncio.Queue = asyncio.Queue()
    pending_blocks: list[dict] = []

    def emit(ui: dict) -> None:
        pending_blocks.append(ui)
        loop.call_soon_threadsafe(out.put_nowait, {"type": "ui", "event": ui})

    tc = ToolContext(ctx=ctx, bundle=bundle, now=now, emit=emit)
    agent = make_agent(bundle.system, make_tools(tc))
    await agent.start()
    await out.put({"type": "ready", "conversation_id": conv})
    stop = asyncio.Event()

    async def sender():
        while True:
            frame = await out.get()
            if frame is None:
                return
            try:
                await ws.send_json(frame)
            except Exception:
                stop.set()
                return

    async def reader():
        try:
            while not stop.is_set():
                msg = await ws.receive_json()
                kind = msg.get("type")
                if kind == "audio" and msg.get("data"):
                    await agent.send(audio_input(base64.b64decode(msg["data"])))
                elif kind == "text" and (msg.get("text") or "").strip():
                    text = msg["text"].strip()[:500]
                    hit = scan(text)
                    if hit.label == "crisis":
                        await out.put({"type": "crisis", **_crisis_card(ctx, bundle, now, hit.codes)})
                        stop.set()
                        return
                    await agent.send(text)
                elif kind == "stop":
                    stop.set()
                    return
        except (WebSocketDisconnect, RuntimeError):
            stop.set()

    async def receiver():
        user_text = ""
        try:
            async for ev in agent.receive():
                t = ev.get("type")
                if t == "bidi_audio_delta":
                    await out.put({"type": "audio", "data": ev["audio"]})
                elif t == "bidi_transcript_delta":
                    await out.put({"type": "transcript", "role": ev.get("role", "assistant"), "text": ev.get("delta", ""), "final": False})
                elif t == "bidi_transcript_block":
                    role, text = ev.get("role", "assistant"), ev.get("transcript", "")
                    if role == "user":
                        hit = scan(text)
                        if hit.label == "crisis":
                            await out.put({"type": "crisis", **_crisis_card(ctx, bundle, now, hit.codes)})
                            stop.set()
                            return
                        user_text = text
                        await asyncio.to_thread(_save, ctx, conv, "user", text, [], now)
                    else:
                        blocks = list(pending_blocks)
                        pending_blocks.clear()
                        await asyncio.to_thread(_save, ctx, conv, "assistant", text, blocks, now)
                    await out.put({"type": "transcript", "role": role, "text": text, "final": True})
                elif t == "bidi_barge_in":
                    await out.put({"type": "barge_in"})
                elif t == "bidi_error":
                    await out.put({"type": "error", "message": "Voice had a problem. Try again or type instead."})
                if stop.is_set():
                    return
        except Exception as exc:
            log.warning("voice receive failed", extra={"err": type(exc).__name__})
            await out.put({"type": "error", "message": "Voice isn't available right now. You can type instead."})
        finally:
            stop.set()
            _ = user_text

    async def pinger():
        while not stop.is_set():
            await asyncio.sleep(PING_EVERY_S)
            await out.put({"type": "ping"})

    started = time.monotonic()
    tasks = [asyncio.create_task(x) for x in (sender(), reader(), receiver(), pinger())]
    try:
        while not stop.is_set() and time.monotonic() - started < SESSION_CAP_S:
            await asyncio.sleep(0.2)
    finally:
        stop.set()
        try:
            await agent.stop()
        except Exception:
            pass
        await out.put({"type": "end"})
        await out.put(None)
        for task in tasks[1:]:
            task.cancel()
        try:
            await asyncio.wait_for(tasks[0], 2)
        except (asyncio.TimeoutError, Exception):
            tasks[0].cancel()
