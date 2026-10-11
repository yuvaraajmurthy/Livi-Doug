import asyncio

from fastapi import APIRouter, WebSocket
from fastapi import HTTPException

from app.auth import parse
from app.voice_ws import session

router = APIRouter(tags=["voice"])


@router.websocket("/voice/ws")
async def voice_ws(ws: WebSocket):
    """Voice mode. First frame: {"type": "start", "token": "<demo token>", "conversation_id": null}. See spec §4."""
    await ws.accept()
    try:
        first = await asyncio.wait_for(ws.receive_json(), 10)
        ctx = parse(str(first.get("token", "")))
        if ctx.role != "student":
            raise HTTPException(403)
    except (asyncio.TimeoutError, HTTPException, ValueError, KeyError):
        await ws.send_json({"type": "error", "message": "Start a student session first."})
        await ws.close(code=4401)
        return
    try:
        await session.run(ws, ctx, first.get("conversation_id"))
    finally:
        try:
            await ws.close()
        except RuntimeError:
            pass
