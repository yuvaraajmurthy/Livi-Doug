import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.auth import SessionCtx, student_session
from app.chat import store
from app.chat.agent import run_turn
from app.db import conn
from app.models.items import ChatNew, ChatRequest

router = APIRouter(tags=["chat"])
log = logging.getLogger("compass.chat")


@router.post("/chat", summary="Chat with Compass (Strands agent). Server-sent events: meta, status, delta, events, plan, "
                              "memory, memory_removed, support, crisis, done, error.")
async def chat(body: ChatRequest, ctx: SessionCtx = Depends(student_session)):
    async def stream():
        try:
            async for event, data in run_turn(ctx, body.message.strip(), body.conversation_id):
                yield f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
        except Exception:  # last resort: never leave the client hanging
            log.exception("chat turn failed")
            yield 'event: error\ndata: {"message": "Compass had trouble answering. Try again."}\n\n'
    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})


@router.get("/chat/history", summary="Turns of a conversation (the latest when conversation_id is omitted)")
def history(conversation_id: str | None = None, ctx: SessionCtx = Depends(student_session)):
    with conn() as c:
        conv = conversation_id or store.latest_conversation(c, ctx.student_id)
        rows = store.messages(c, ctx.student_id, conv) if conv else []
    return {"conversation_id": conv, "messages": [
        {"id": r["id"], "role": r["role"], "text": r["text"], "blocks": r["blocks"], "source": r["source"],
         "at": r["created_at"].isoformat()} for r in rows]}


@router.post("/chat/new", response_model=ChatNew, summary="Start a new conversation (memory is kept)")
def new_chat(ctx: SessionCtx = Depends(student_session)):
    from app.chat import memory
    with conn() as c:
        old = store.latest_conversation(c, ctx.student_id)
        if old and store.user_turns(c, ctx.student_id, old) % memory.FLUSH_EVERY:
            from app.chat.agent import models_available
            if models_available():
                memory.flush(c, ctx.student_id, old)
        conv = store.start(c, ctx.student_id)
    return ChatNew(conversation_id=conv)
