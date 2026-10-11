"""Demo session tokens: 'v1.<persona>.<sid>.<sig>' signed with HMAC-SHA256.

The token carries the persona so fixture mode works with no database. In a pilot this is
replaced by Rutgers SSO and a hashed subject; nothing else in the app changes.
"""
import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass

from fastapi import Header, HTTPException

from config.settings import get_settings

PERSONA_STUDENT = {
    "andre": "DEMO-ANDRE",
    "priya": "DEMO-PRIYA",
    "taylor": "DEMO-TAYLOR",
    "sofia": "DEMO-SOFIA",
    "jordan": "DEMO-JORDAN",
}


SANDBOX_PREFIX = "sb"


@dataclass(frozen=True)
class SessionCtx:
    token: str
    persona: str
    sid: str

    @property
    def role(self) -> str:
        return "staff" if self.persona == "staff" else "student"

    @property
    def sandbox(self) -> bool:
        """Table-mode tours run on a private clone of the persona; the marker lives in the signed sid."""
        return self.sid.startswith(SANDBOX_PREFIX)

    @property
    def student_id(self) -> str | None:
        base = PERSONA_STUDENT.get(self.persona)
        return f"{base}~{self.sid}" if base and self.sandbox else base


def _sig(payload: str) -> str:
    key = get_settings().demo_signing_key.encode()
    digest = hmac.new(key, payload.encode(), hashlib.sha256).digest()[:18]
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def issue(persona: str, sandbox: bool = False) -> SessionCtx:
    sid = secrets.token_urlsafe(9)
    if sid.startswith(SANDBOX_PREFIX):  # plain sids must never look like sandbox sids
        sid = "x" + sid[1:]
    if sandbox:
        sid = SANDBOX_PREFIX + sid
    payload = f"v1.{persona}.{sid}"
    return SessionCtx(token=f"{payload}.{_sig(payload)}", persona=persona, sid=sid)


def parse(token: str) -> SessionCtx:
    parts = token.split(".")
    if len(parts) != 4 or parts[0] != "v1":
        raise HTTPException(401, detail={"error": "bad_token", "message": "Unknown session. Start a demo session."})
    payload = ".".join(parts[:3])
    if not hmac.compare_digest(_sig(payload), parts[3]):
        raise HTTPException(401, detail={"error": "bad_token", "message": "Unknown session. Start a demo session."})
    persona = parts[1]
    if persona not in PERSONA_STUDENT and persona != "staff":
        raise HTTPException(401, detail={"error": "bad_token", "message": "Unknown persona."})
    return SessionCtx(token=token, persona=persona, sid=parts[2])


def session(authorization: str | None = Header(None)) -> SessionCtx:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, detail={"error": "no_token", "message": "Send Authorization: Bearer <demo session token>."})
    return parse(authorization.split(" ", 1)[1].strip())


def student_session(authorization: str | None = Header(None)) -> SessionCtx:
    ctx = session(authorization)
    if ctx.role != "student":
        raise HTTPException(403, detail={"error": "student_only", "message": "This route needs a student session."})
    return ctx


def staff_session(authorization: str | None = Header(None)) -> SessionCtx:
    ctx = session(authorization)
    if ctx.role != "staff":
        raise HTTPException(403, detail={"error": "staff_only", "message": "This route needs a staff session."})
    return ctx
