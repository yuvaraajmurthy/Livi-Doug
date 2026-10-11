"""Commitment lifecycle: I'm in -> plan + calendar + reminder + invite -> follow-up -> Arc, challenge, memory, next rung."""
import hashlib
import secrets
from datetime import datetime

from fastapi import HTTPException

from app import clock
from app.auth import SessionCtx
from app.db import conn
from app.engine import care_first as cf
from app.engine.rank import cfg as engine_cfg
from app.llm import wording
from app.loop import arc, ics as icsmod, notify
from app.memory import rules as mem
from app.models.common import GoingCount, Item, Place
from app.models.loop import (
    ArcStatus, ChallengeProgress, CommitRequest, CommitResponse, FollowupRequest, FollowupResponse, InviteAccepted,
    InviteView, NextRung, ProgressDelta,
)
from app.models.student import MemoryItem, MemorySource
from app.repo import kb
from app.safety import crisis
from app.safety.check import check_text, record_event
from app.services import present
from app.services.present import clock_label

DAY_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _item_dict(i) -> dict:
    return {"id": i.id, "title": i.title, "venue": i.venue, "starts_at": i.starts_at, "ends_at": i.ends_at,
            "formats": sorted(i.formats), "series_key": i.series_key, "causes": sorted(i.causes)}


def _api_item(i, lang: str) -> Item:
    summary = i.summary_es if lang == "es" and i.summary_es else i.summary
    return Item(id=i.id, kind=i.kind, title=i.title, summary=summary, dimensions=[d for d in i.dims], url=i.url,
                phone=i.phone, hours_text=i.hours_text, synthetic=i.synthetic)


def _place(i) -> Place:
    campus = i.campus if i.campus in ("new_brunswick", "newark", "camden", "online", "community") else "online"
    return Place(venue=i.venue, address=i.address, lat=i.lat, lon=i.lon, campus=campus)


def _when(i, lang: str) -> str:
    from app.engine.types import Scored
    fake = Scored(item=i, score=0, components={}, component_text={}, filters=[], memory=[], walk_min=None, window_label=None, distance_note=None)
    return present.when_label(fake, lang)


def _plan_facts(i, windows: list[str]) -> dict:
    f = {"title": i.title.replace(" (sample)", ""), "venue": i.venue, "kind": i.kind}
    if i.starts_at:
        f["weekday"] = i.starts_at.strftime("%A")
        f["weekday_es"] = DAY_ES[i.starts_at.weekday()]
        f["start_label"] = f"{clock_label(i.starts_at)} {'AM' if i.starts_at.hour < 12 else 'PM'}"
        from app.engine.rank import parse_window
        for w in windows:
            pw = parse_window(w)
            if pw and pw.weekday == i.starts_at.weekday() and pw.start <= i.starts_at.time() <= pw.end:
                f["window_start_label"] = f"{pw.start.hour % 12 or 12}:{pw.start.minute:02d}"
    return f


def commit(ctx: SessionCtx, body: CommitRequest):
    student_text = (body.plan_text or "").strip()
    verdict = check_text(student_text) if student_text else None
    with conn() as c:
        now = clock.now(c, ctx.sid)
        s = c.execute("SELECT * FROM students WHERE id = %s", (ctx.student_id,)).fetchone()
        p = c.execute("SELECT * FROM profiles WHERE student_id = %s", (ctx.student_id,)).fetchone() or {}
        lang = p.get("language") or "en"
        if verdict and verdict.label == "crisis":
            record_event(c, ctx.student_id, "plan_text", verdict, "crisis_card")
            return crisis.crisis_response(c, s["campus"], lang, now)
        rec = c.execute("SELECT * FROM recommendations WHERE id = %s AND student_id = %s", (body.rec_id, ctx.student_id)).fetchone()
        if not rec:
            raise HTTPException(404, detail={"error": "not_found", "message": "No such suggestion for this student."})
        existing = c.execute("SELECT * FROM commitments WHERE recommendation_id = %s", (rec["id"],)).fetchone()
        item = kb.load_items(c, s["campus"], now, ids=[rec["item_id"]])[0]
        if existing:
            return _commit_response(c, existing, item, now, lang)
        if item.starts_at and item.starts_at <= now:
            raise HTTPException(409, detail={"error": "already_started", "message": "That one has already started. Try another step."})
        if verdict and verdict.label == "none" and student_text:
            plan_text, plan_source = student_text, "student"
        else:
            plan_text, src = wording.get(c, "plan", _plan_facts(item, p.get("free_windows") or []), lang)
            plan_source = "ai" if src == "ai" else "template"
        cm = c.execute(
            """INSERT INTO commitments (recommendation_id, student_id, item_id, if_then_plan, plan_source, status, starts_at, ends_at, planned_at, created_at)
               VALUES (%s, %s, %s, %s, %s, 'planned', %s, %s, %s, %s) RETURNING *""",
            (rec["id"], ctx.student_id, item.id, plan_text, plan_source, item.starts_at, item.ends_at, now, now)).fetchone()
        c.execute("UPDATE recommendations SET status = 'committed' WHERE id = %s", (rec["id"],))
        c.execute("INSERT INTO invites (commitment_id, token) VALUES (%s, %s)", (cm["id"], secrets.token_urlsafe(9)))
        scores, _ = kb.latest_scores(c, ctx.student_id, now)
        r_at, f_at = notify.schedule_for_commitment(c, ctx.student_id, cm["id"], _item_dict(item), now, lang, cf.applies(scores))
        c.execute("UPDATE commitments SET reminder_at = %s, followup_at = %s WHERE id = %s", (r_at, f_at, cm["id"]))
        cm = c.execute("SELECT * FROM commitments WHERE id = %s", (cm["id"],)).fetchone()
        return _commit_response(c, cm, item, now, lang)


def _commit_response(c, cm: dict, item, now: datetime, lang: str) -> CommitResponse:
    inv = c.execute("SELECT token FROM invites WHERE commitment_id = %s ORDER BY id LIMIT 1", (cm["id"],)).fetchone()
    token = inv["token"]
    when = _when(item, lang)
    title = item.title
    share = (f"Voy a {title.replace(' (sample)', '')} ({when}). ¿Vienes conmigo?" if lang == "es"
             else f"I'm going to {title.replace(' (sample)', '')} ({when}). Come with me?")
    return CommitResponse(
        synthetic=bool(item.synthetic) or True, now=now, commitment_id=cm["id"], status=cm["status"], item=_api_item(item, lang),
        when_label=when, where=_place(item), plan_text=cm["if_then_plan"], plan_source=cm["plan_source"] or "template",
        ics_url=f"/commitments/{cm['id']}/ics?t={token}",
        google_calendar_url=icsmod.google_url(title, item.starts_at, item.ends_at, item.address or item.venue, cm["if_then_plan"]),
        reminder_at=cm["reminder_at"], followup_at=cm["followup_at"], invite_url=f"/i/{token}", invite_token=token, share_text=share)


def ics(commitment_id: int, token: str) -> str:
    with conn() as c:
        row = c.execute(
            """SELECT cm.*, i.title, i.venue, i.address FROM commitments cm JOIN invites v ON v.commitment_id = cm.id
               JOIN kb_items i ON i.id = cm.item_id WHERE cm.id = %s AND v.token = %s""", (commitment_id, token)).fetchone()
        if not row:
            raise HTTPException(404, detail={"error": "not_found", "message": "Unknown calendar link."})
        now = clock.now(c, None)
        uid = hashlib.sha256(f"{commitment_id}".encode()).hexdigest()[:16]
        return icsmod.build(uid, row["title"], clock.to_ny(row["starts_at"]) if row["starts_at"] else None,
                            clock.to_ny(row["ends_at"]) if row["ends_at"] else None, row["address"] or row["venue"],
                            row["if_then_plan"] or "", now)


def _invite_row(c, token: str) -> dict:
    row = c.execute("SELECT v.*, cm.item_id, cm.student_id FROM invites v JOIN commitments cm ON cm.id = v.commitment_id WHERE v.token = %s",
                    (token,)).fetchone()
    if not row:
        raise HTTPException(404, detail={"error": "not_found", "message": "This invite link isn't valid any more."})
    return row


def invite_view(token: str) -> InviteView:
    """Public. Event details only: nothing about the inviter."""
    with conn() as c:
        row = _invite_row(c, token)
        now = clock.now(c, None)
        item = kb.load_items(c, "online", now, ids=[row["item_id"]])[0]
        n = kb.going_count(c, item.id)
        going = GoingCount(count=n, label=f"{n} students are going") if n >= 5 else GoingCount(count=None, label="A few students are going" if n else "")
        return InviteView(synthetic=bool(item.synthetic), now=now, token=token, item=_api_item(item, "en"), when_label=_when(item, "en"),
                          where=_place(item), going=going, accepted=row["accepted_at"] is not None)


def invite_accept(token: str) -> InviteAccepted:
    with conn() as c:
        row = _invite_row(c, token)
        now = clock.now(c, None)
        if row["accepted_at"] is None:
            c.execute("UPDATE invites SET accepted_at = %s, opened_at = coalesce(opened_at, %s) WHERE id = %s", (now, now, row["id"]))
            c.execute("UPDATE commitments SET with_friend = true WHERE id = %s", (row["commitment_id"],))
        return InviteAccepted(synthetic=True, now=now, token=token, accepted=True,
                              ics_url=f"/commitments/{row['commitment_id']}/ics?t={token}", message="You're in. See you there.")


def _challenges_for(c, student: dict, dimension: str | None, day) -> list[dict]:
    return c.execute(
        """SELECT * FROM challenges WHERE starts_on <= %s AND ends_on >= %s AND group_size >= 10
             AND (scope = 'all' OR (scope = 'campus' AND scope_value = %s) OR (scope = 'hall' AND scope_value = %s AND %s = 'resident'))
             AND (dimension IS NULL OR dimension = %s)
           ORDER BY scope = 'campus' DESC, id""",
        (day, day, student["campus"], student["home_area"], student["housing"], dimension)).fetchall()


def challenge_progress(c, ch: dict) -> int:
    r = c.execute("SELECT coalesce(sum(weight), 0) AS n FROM challenge_steps WHERE challenge_id = %s", (ch["id"],)).fetchone()
    return int(ch["base_progress"]) + int(r["n"])


def followup(ctx: SessionCtx, commitment_id: int, body: FollowupRequest) -> FollowupResponse:
    with conn() as c:
        now = clock.now(c, ctx.sid)
        cm = c.execute("SELECT * FROM commitments WHERE id = %s AND student_id = %s", (commitment_id, ctx.student_id)).fetchone()
        if not cm:
            raise HTTPException(404, detail={"error": "not_found", "message": "No such plan for this student."})
        if cm["status"] != "planned":
            raise HTTPException(409, detail={"error": "already_answered", "message": "You already told us how this went."})
        if cm["starts_at"] and clock.to_ny(cm["starts_at"]) > now:
            raise HTTPException(409, detail={"error": "too_early", "message": "This hasn't happened yet."})
        s = c.execute("SELECT * FROM students WHERE id = %s", (ctx.student_id,)).fetchone()
        p = c.execute("SELECT * FROM profiles WHERE student_id = %s", (ctx.student_id,)).fetchone() or {}
        lang = p.get("language") or "en"
        item = kb.load_items(c, s["campus"], now, ids=[cm["item_id"]])[0]
        helped = body.helped if body.went else None
        c.execute("INSERT INTO feedback (commitment_id, student_id, went, helped, created_at) VALUES (%s, %s, %s, %s, %s)",
                  (cm["id"], ctx.student_id, body.went, helped, now))
        c.execute("UPDATE commitments SET status = %s WHERE id = %s", ("went" if body.went else "missed", cm["id"]))
        c.execute("UPDATE notifications SET status = 'cancelled' WHERE commitment_id = %s AND kind = 'followup' AND status = 'scheduled'", (cm["id"],))
        focus = p.get("focus_dimension") or "social"
        arc_status = ArcStatus(status="none", message="")
        challenge = None
        next_rung = None
        learned_ids: list[int] = []
        if body.went:
            pseudonym = hashlib.sha256(f"compass:{ctx.student_id}".encode()).hexdigest()[:16]
            res = arc.adapter().record_attendance(pseudonym, item.arc_activity_id, now)
            c.execute("INSERT INTO arc_credits (commitment_id, arc_activity_id, status, occurred_at) VALUES (%s, %s, %s, %s)",
                      (cm["id"], item.arc_activity_id, res.status, now))
            arc_status = ArcStatus(status=res.status, message=res.message if lang == "en" else "Crédito de bienestar agregado a The Arc (demo)")
            weight = 2 if cm["with_friend"] else 1
            chs = _challenges_for(c, s, focus, now.date())
            for ch in chs:
                c.execute("INSERT INTO challenge_steps (challenge_id, commitment_id, weight) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                          (ch["id"], cm["id"], weight))
            if chs:
                ch = chs[0]
                prog = challenge_progress(c, ch)
                challenge = ChallengeProgress(challenge_id=ch["id"], title=ch["title"], added=weight, progress=prog,
                                              goal=ch["goal_steps"], pct=round(min(1.0, prog / ch["goal_steps"]), 3))
            learned_ids = mem.on_feedback(c, ctx.student_id, _item_dict(item), True, helped, now)
            rung = p.get("social_rung") or 1
            if helped is not None and helped >= 4 and focus == "social" and rung < 3:
                new = min(3, rung + engine_cfg()["rung_after_good_rating"])
                c.execute("UPDATE profiles SET social_rung = %s, rung_reason = 'rated' WHERE student_id = %s", (new, ctx.student_id))
                learned_ids.append(mem.on_rung(c, ctx.student_id, new, now))
                labels = engine_cfg()["rung_labels_es" if lang == "es" else "rung_labels"]
                next_rung = NextRung(rung=new, label=labels[new],
                                     message=("Eso salió bien. ¿Listo para algo un poco más abierto la próxima semana?" if lang == "es"
                                              else "That went well. Ready to try something a bit more open next week?"))
        month_start = now.date().replace(day=1)
        steps = c.execute("""SELECT count(*) AS n FROM commitments cm JOIN feedback f ON f.commitment_id = cm.id
                             WHERE cm.student_id = %s AND f.went AND f.created_at >= %s""", (ctx.student_id, month_start)).fetchone()["n"]
        progress = ProgressDelta(dimension=focus, steps_this_month=steps,
                                 message=(f"{steps} paso(s) este mes. Cuenta." if lang == "es" else
                                          f"{steps} step{'s' if steps != 1 else ''} taken this month. That counts.")) if body.went else None
        learned = []
        if learned_ids:
            for m in c.execute("SELECT * FROM student_memory WHERE id = ANY(%s) ORDER BY id", (learned_ids,)).fetchall():
                learned.append(MemoryItem(id=f"m:{m['id']}", kind=m["kind"], statement=m["statement_es"] if lang == "es" and m["statement_es"] else m["statement"],
                                          source=MemorySource(type=m["source_type"], label=m["source_label"], at=m["updated_at"]),
                                          used_for=m["used_for"], learned_at=m["created_at"], last_used_at=m["last_used_at"]))
        return FollowupResponse(synthetic=True, now=now, commitment_id=cm["id"], status="went" if body.went else "missed",
                                progress=progress, arc=arc_status, challenge=challenge, next_rung=next_rung, learned=learned,
                                win_prompt=bool(body.went))
