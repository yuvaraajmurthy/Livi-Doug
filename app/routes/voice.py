"""Voice (P2): OpenAI-compatible chat completions for ElevenLabs Agents' "custom LLM" option.

ElevenLabs is only ears and mouth. Every transcript goes through the same crisis check and the same scoped Ask
pipeline; there is no second AI brain and no open-ended chat. Identity: the demo session token is configured as the
custom LLM's API key, so it arrives as `Authorization: Bearer <token>`. A short buffer phrase is streamed first so
the voice never sits silent while retrieval runs."""
import json
import time
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app import clock
from app.auth import SessionCtx, student_session
from app.db import conn
from app.safety import crisis
from app.safety.check import check_text, record_event

router = APIRouter(tags=["p2"])
BUFFER = {"en": "Okay, one sec... ", "es": "Un momento... "}


def _spoken_crisis(c, campus: str, lang: str) -> str:
    lines = crisis.crisis_lines(c, campus, lang)
    title, message = crisis.COPY.get(lang, crisis.COPY["en"])
    contacts = "; ".join(f"{l.name}: {l.contact}" for l in lines[:4])
    return f"{title}. {message} {contacts}."


def _answer(ctx: SessionCtx, text: str) -> tuple[str, str]:
    from app.ask.service import answer
    verdict = check_text(text)
    with conn() as c:
        s = c.execute("SELECT campus FROM students WHERE id = %s", (ctx.student_id,)).fetchone()
        p = c.execute("SELECT language FROM profiles WHERE student_id = %s", (ctx.student_id,)).fetchone() or {}
        lang = p.get("language") or "en"
        if verdict.label == "crisis":
            record_event(c, ctx.student_id, "voice", verdict, "crisis_card")
            return _spoken_crisis(c, s["campus"], lang), lang
        now = clock.now(c, ctx.sid)
        res = answer(c, text, s["campus"], now, lang)
        return res["text"], lang


def _chunk(cid: str, model: str, content: str | None, finish: str | None = None) -> str:
    delta = {"content": content} if content is not None else {}
    return "data: " + json.dumps({"id": cid, "object": "chat.completion.chunk", "created": int(time.time()), "model": model,
                                  "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}) + "\n\n"


@router.post("/v1/chat/completions", summary="OpenAI-compatible endpoint for ElevenLabs custom LLM (crisis-checked, scoped)")
async def chat_completions(request: Request, ctx: SessionCtx = Depends(student_session)):
    body = await request.json()
    msgs = [m for m in body.get("messages", []) if m.get("role") == "user"]
    text = (msgs[-1].get("content") if msgs else "") or ""
    if isinstance(text, list):  # content parts
        text = " ".join(p.get("text", "") for p in text if isinstance(p, dict))
    text = text[:500]
    model = body.get("model") or "compass-voice"
    cid = "chatcmpl-" + uuid.uuid4().hex[:12]
    if not body.get("stream"):
        from starlette.concurrency import run_in_threadpool
        reply, _ = await run_in_threadpool(_answer, ctx, text)
        return JSONResponse({"id": cid, "object": "chat.completion", "created": int(time.time()), "model": model,
                             "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}]})

    async def stream():
        from starlette.concurrency import run_in_threadpool
        yield _chunk(cid, model, None)
        yield _chunk(cid, model, BUFFER["en"])
        reply, _ = await run_in_threadpool(_answer, ctx, text)
        words = reply.split(" ")
        for i in range(0, len(words), 6):
            yield _chunk(cid, model, " ".join(words[i:i + 6]) + " ")
        yield _chunk(cid, model, None, "stop")
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
