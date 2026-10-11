"""Campus pulse: cooperative challenges (groups of 10+ only) and the anonymous wins wall."""
import secrets

from fastapi import HTTPException

from app import clock
from app.auth import SessionCtx
from app.db import conn
from app.models.social import Challenge, PulseResponse, SameHere, Win, WinAccepted, WinRequest
from app.safety import crisis
from app.safety.check import check_text, record_event
from app.safety.moderation import moderate
from app.services.loop import challenge_progress


def pulse(ctx: SessionCtx) -> PulseResponse:
    with conn() as c:
        now = clock.now(c, ctx.sid)
        s = c.execute("SELECT * FROM students WHERE id = %s", (ctx.student_id,)).fetchone()
        rows = c.execute(
            """SELECT * FROM challenges WHERE group_size >= 10 AND ends_on >= %s AND starts_on <= %s + 14
                 AND (scope = 'all' OR (scope = 'campus' AND scope_value = %s) OR (scope = 'hall' AND scope_value = %s))
               ORDER BY starts_on, scope = 'campus' DESC, id""",
            (now.date(), now.date(), s["campus"], s["home_area"])).fetchall()
        chs = []
        for ch in rows:
            prog = challenge_progress(c, ch)
            mine = ch["scope"] in ("all", "campus") or (ch["scope"] == "hall" and s["housing"] == "resident")
            chs.append(Challenge(id=ch["id"], title=ch["title"], scope=ch["scope"], scope_label=ch["scope_label"] or ch["scope"],
                                 dimension=ch["dimension"], goal=ch["goal_steps"], progress=prog, pct=round(min(1.0, prog / ch["goal_steps"]), 3),
                                 starts_on=ch["starts_on"], ends_on=ch["ends_on"], rule=ch["rule"], yours=mine, synthetic=ch["synthetic"]))
        wins = c.execute(
            """SELECT id, text, dimension, campus, same_here, created_at, synthetic FROM wins
               WHERE status = 'approved' AND (campus = %s OR campus IS NULL OR %s) ORDER BY created_at DESC, same_here DESC LIMIT 20""",
            (s["campus"], True)).fetchall()
        return PulseResponse(synthetic=True, now=now, challenges=chs,
                             wins=[Win(id=w["id"], text=w["text"], dimension=w["dimension"], campus=w["campus"], same_here=w["same_here"],
                                       created_at=w["created_at"], synthetic=w["synthetic"]) for w in wins])


def post_win(ctx: SessionCtx, body: WinRequest):
    """Pipeline: crisis check -> rules -> model -> publish. A crisis post is never published."""
    # Moderation runs in parallel with the crisis check; its result is used only if the check says 'none'.
    from app.safety.check import POOL as _POOL
    from app.safety.lexicon import scan
    mod_future = None if scan(body.text).label == "crisis" else _POOL.submit(moderate, body.text)
    verdict = check_text(body.text)
    with conn() as c:
        now = clock.now(c, ctx.sid)
        s = c.execute("SELECT * FROM students WHERE id = %s", (ctx.student_id,)).fetchone()
        lang = (c.execute("SELECT language FROM profiles WHERE student_id = %s", (ctx.student_id,)).fetchone() or {}).get("language") or "en"
        wid = "w-" + secrets.token_hex(5)
        if verdict.label == "crisis":
            record_event(c, ctx.student_id, "wins_post", verdict, "not_published_private_card")
            # Never store the text of a crisis-flagged post.
            return crisis.crisis_response(c, s["campus"], lang, now)
        if verdict.label == "concern":
            record_event(c, ctx.student_id, "wins_post", verdict, "held")
            c.execute("INSERT INTO wins (id, student_id, campus, dimension, text, status, moderation_code, created_at) VALUES (%s, %s, %s, %s, %s, 'held', 'concern', %s)",
                      (wid, ctx.student_id, s["campus"], body.dimension, body.text, now))
            return WinAccepted(synthetic=True, now=now, kind="held", win_id=wid,
                               message="Thanks. A person will look at this before it goes up.")
        try:
            decision, code = mod_future.result(timeout=2.0)  # type: ignore[union-attr]
        except Exception:
            from app.safety.moderation import rules
            decision, code = rules(body.text)
            decision = "hold" if decision == "approve" else decision  # model unavailable and unchecked: a person looks first
        status = {"approve": "approved", "hold": "held", "reject": "rejected"}[decision]
        c.execute("INSERT INTO wins (id, student_id, campus, dimension, text, status, moderation_code, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                  (wid, ctx.student_id, s["campus"], body.dimension, body.text, status, code, now))
        msg = {"approved": "Posted. Thanks for sharing.",
               "held": "Thanks. A person will look at this before it goes up (we keep the wall anonymous).",
               "rejected": "This one can't go on the wall. Keep it about your own small step."}[status]
        return WinAccepted(synthetic=True, now=now, kind={"approved": "accepted", "held": "held", "rejected": "rejected"}[status],
                           win_id=wid, message=msg)


def same_here(ctx: SessionCtx, win_id: str) -> SameHere:
    with conn() as c:
        now = clock.now(c, ctx.sid)
        w = c.execute("SELECT id FROM wins WHERE id = %s AND status = 'approved'", (win_id,)).fetchone()
        if not w:
            raise HTTPException(404, detail={"error": "not_found", "message": "No such win."})
        ins = c.execute("INSERT INTO win_reactions (win_id, student_id) VALUES (%s, %s) ON CONFLICT DO NOTHING RETURNING win_id",
                        (win_id, ctx.student_id)).fetchone()
        if ins:
            c.execute("UPDATE wins SET same_here = same_here + 1 WHERE id = %s", (win_id,))
        n = c.execute("SELECT same_here FROM wins WHERE id = %s", (win_id,)).fetchone()["same_here"]
        return SameHere(synthetic=True, now=now, win_id=win_id, same_here=n)
