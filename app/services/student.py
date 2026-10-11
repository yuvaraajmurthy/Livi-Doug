"""Student flow: map, focus, next step, decline, card, memory, forget me, inbox."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta

from fastapi import HTTPException

from app import clock
from app.auth import SessionCtx
from app.db import conn
from app.engine import care_first as cf
from app.engine.rank import cfg as engine_cfg, rank
from app.memory import rules as mem
from app.models.student import (
    CardResponse, DeleteResult, DimensionScore, FocusRequest, InboxItem, InboxResponse, MapResponse, MemoryItem,
    MemoryList, MemorySource, NextResponse, Profile, ProfileResult, RetakeNudge, StudentSummary, Take,
)
from app.repo import kb
from app.safety import crisis
from app.safety.barrier_map import map_text
from app.safety.check import check_text, record_event
from app.services import present
from app.services.meta import barrier_meta  # noqa: F401  (re-exported for routes)

_EXEC = ThreadPoolExecutor(max_workers=8, thread_name_prefix="focus")


def _now(c, ctx: SessionCtx) -> datetime:
    return clock.now(c, ctx.sid)


def _student(c, sid: str) -> dict:
    s = c.execute("SELECT * FROM students WHERE id = %s", (sid,)).fetchone()
    if not s:
        raise HTTPException(404, detail={"error": "forgotten", "message": "This student was deleted. Start a new demo session or reset."})
    return s


def _profile(c, sid: str) -> dict:
    p = c.execute("SELECT * FROM profiles WHERE student_id = %s", (sid,)).fetchone()
    if not p:
        c.execute("INSERT INTO profiles (student_id) VALUES (%s)", (sid,))
        p = c.execute("SELECT * FROM profiles WHERE student_id = %s", (sid,)).fetchone()
    return p


def _profile_model(p: dict) -> Profile:
    return Profile(focus=p.get("focus_dimension"), barriers=p.get("barriers") or [], barriers_from_text=p.get("barriers_from_text") or [],
                   free_windows=p.get("free_windows") or [], social_rung=p.get("social_rung") or 1,
                   free_only=p.get("free_only", True), language=p.get("language") or "en")


# ------------------------------------------------------------------------------------------ map
def _fresh_start(now: datetime) -> bool:
    d = now.date()
    after_midterms = datetime(2026, 11, 2).date() <= d <= datetime(2026, 11, 8).date()
    return d.weekday() == 0 or d.day == 1 or after_midterms


def get_map(ctx: SessionCtx) -> MapResponse:
    with conn() as c:
        now = _now(c, ctx)
        s = _student(c, ctx.student_id)
        p = _profile(c, ctx.student_id)
        scores, takes = kb.latest_scores(c, ctx.student_id, now)
        if not takes:
            raise HTTPException(404, detail={"error": "no_scores", "message": "No inventory results yet."})
        lang = p.get("language") or "en"
        sc = cf.scoring()
        prev = takes[-2]["scores"] if len(takes) > 1 else None
        dims = sorted(scores, key=lambda d: (-scores[d], d))
        care = cf.applies(scores)
        if care:
            _log_care_first(c, ctx.student_id, now)
        last = takes[-1]["taken_on"]
        nudge = None
        if _fresh_start(now) and (now.date() - last).days >= 28:
            nudge = RetakeNudge(show=True, message=("Nuevo comienzo: vuelve a hacer el inventario en MyRutgers para ver tu avance."
                                                     if lang == "es" else "Fresh start: retake the inventory in MyRutgers to see what's changed."))
        return MapResponse(
            synthetic=bool(s["synthetic"]), now=now,
            student=StudentSummary(id=s["id"], persona=ctx.persona, campus=s["campus"], level=s["level"], housing=s["housing"], language=lang),
            latest=Take(take_no=takes[-1]["take_no"], taken_on=last, total=takes[-1]["total"], scores=scores),
            dimensions=[DimensionScore(dimension=d, label=sc["labels"][lang][d], score=scores[d], band=cf.band(scores[d]),
                                       blurb=sc["blurbs"][lang][cf.band(scores[d])],
                                       change=round(scores[d] - prev[d], 2) if prev and d in prev else None) for d in dims],
            strengths=[d for d in dims if cf.band(scores[d]) == "high"][:3] or dims[:1],
            growth_areas=[d for d in dims if cf.band(scores[d]) == "low"],
            care_first=care,
            previous_takes=[Take(take_no=t["take_no"], taken_on=t["taken_on"], total=t["total"], scores=t["scores"]) for t in takes[:-1]],
            profile=_profile_model(p), retake_nudge=nudge,
        )


def _log_care_first(c, sid: str, now: datetime) -> None:
    """Record that care-first applied (never the scores), at most once per simulated day."""
    seen = c.execute("SELECT 1 FROM safety_events WHERE student_id = %s AND level = 'care_first' AND created_at::date = %s",
                     (sid, now.date())).fetchone()
    if not seen:
        c.execute("INSERT INTO safety_events (student_id, source, level, action, stage, created_at) VALUES (%s, 'score_rule', 'care_first', 'support_card_first', 'rule', %s)",
                  (sid, now))


# ------------------------------------------------------------------------------------------ focus
def set_focus(ctx: SessionCtx, body: FocusRequest):
    text = (body.text or "").strip()
    verdict = None
    mapped: tuple[list[str], list[str], str] = ([], [], "none")
    if text:
        # Stage-1 code check runs before any model sees the text. Only if it passes do the stage-2 labellers and the
        # barrier mapper run (in parallel); the mapping is discarded unless the final verdict is 'none'.
        from app.safety.lexicon import scan
        if scan(text).label == "crisis":
            verdict = check_text(text, use_classifier=False)
            fut_map = None
        else:
            fut_map = _EXEC.submit(map_text, text)
            verdict = check_text(text)
        if verdict.label == "none":
            try:
                mapped = fut_map.result(timeout=2.0)
            except Exception:
                from app.safety.barrier_map import keyword_map
                b, cc = keyword_map(text)
                mapped = (b, cc, "keyword")
        elif fut_map is not None:
            fut_map.cancel()
    with conn() as c:
        now = _now(c, ctx)
        s = _student(c, ctx.student_id)
        p = _profile(c, ctx.student_id)
        lang = p.get("language") or "en"
        if verdict and verdict.label == "crisis":
            record_event(c, ctx.student_id, "barrier_text", verdict, "crisis_card")
            return crisis.crisis_response(c, s["campus"], lang, now, synthetic=bool(s["synthetic"]))
        support = None
        if verdict and verdict.label == "concern":
            record_event(c, ctx.student_id, "barrier_text", verdict, "support_offer")
            support = crisis.support_card(s["campus"], lang, kind="concern")
        barriers = list(dict.fromkeys(body.barriers))
        rung = p.get("social_rung") or 1
        rung_reason = p.get("rung_reason")
        if body.dimension == "social" and "dont_know_anyone" in barriers + mapped[0] and rung < 2 and rung_reason != "rated":
            rung, rung_reason = 2, "dont_know_anyone"
        c.execute(
            """UPDATE profiles SET focus_dimension = %s, barriers = %s, barriers_from_text = %s, social_rung = %s, rung_reason = %s,
                   free_only = coalesce(%s, free_only), free_windows = coalesce(%s, free_windows), updated_at = %s
               WHERE student_id = %s""",
            (body.dimension, barriers, mapped[0], rung, rung_reason, body.free_only, body.free_windows, now, ctx.student_id))
        if mapped[1]:
            mem.on_constraints(c, ctx.student_id, mapped[1], now)
        p = _profile(c, ctx.student_id)
        return ProfileResult(synthetic=bool(s["synthetic"]), now=now, profile=_profile_model(p), support=support)


# ------------------------------------------------------------------------------------------ next
def _rank(c, ctx: SessionCtx, now: datetime):
    scores, _ = kb.latest_scores(c, ctx.student_id, now)
    care = cf.applies(scores)
    sctx = kb.student_ctx(c, ctx.student_id, now, care)
    if not sctx.focus:
        weakest = min(scores, key=scores.get) if scores else "social"
        sctx = replace(sctx, focus=weakest)
    items = kb.load_items(c, sctx.campus, now, engine_cfg()["horizon_days"])
    stats = kb.helped_stats(c, sctx, now)
    memory = kb.memory_facts(c, ctx.student_id)
    return sctx, rank(sctx, items, stats, memory, now)


def get_next(ctx: SessionCtx) -> NextResponse:
    with conn() as c:
        now = _now(c, ctx)
        s = _student(c, ctx.student_id)
        sctx, result = _rank(c, ctx, now)
        if not result.picks:
            raise HTTPException(500, detail={"error": "empty", "message": "No suggestion available."})
        pushed = not result.care_first
        set_id, rec_ids = present.persist_set(c, sctx, result, now, pushed, result.engine_version)
        used = {f.id for p in result.picks for f, _ in p.memory}
        if used:
            c.execute("UPDATE student_memory SET last_used_at = %s WHERE id = ANY(%s)", (now, list(used)))
        sugg = [present.suggestion(c, p, rid, sctx, pushed) for p, rid in zip(result.picks, rec_ids)]
        return NextResponse(
            synthetic=bool(s["synthetic"]) or any(x.item.synthetic for x in sugg), now=now, set_id=set_id,
            care_first=result.care_first,
            support_card=crisis.support_card(sctx.campus, sctx.language) if result.care_first else None,
            pick=sugg[0], alternates=sugg[1:], crisis_lines=crisis.crisis_lines(c, sctx.campus, sctx.language),
        )


def decline(ctx: SessionCtx, rec_id: int, body) -> NextResponse:
    with conn() as c:
        now = _now(c, ctx)
        r = c.execute("SELECT r.id, r.item_id, i.title FROM recommendations r JOIN kb_items i ON i.id = r.item_id WHERE r.id = %s AND r.student_id = %s",
                      (rec_id, ctx.student_id)).fetchone()
        if not r:
            raise HTTPException(404, detail={"error": "not_found", "message": "No such suggestion for this student."})
        c.execute("UPDATE recommendations SET status = 'dismissed' WHERE student_id = %s AND item_id = %s AND status = 'shown'",
                  (ctx.student_id, r["item_id"]))
        mem.on_decline(c, ctx.student_id, {"id": r["item_id"], "title": r["title"]}, now)
    return get_next(ctx)


def get_card(ctx: SessionCtx) -> CardResponse:
    nxt = get_next(ctx)
    if nxt.care_first and nxt.support_card:
        return CardResponse(synthetic=nxt.synthetic, now=nxt.now, kind="support", title=nxt.support_card.title,
                            line=nxt.support_card.options[0].name, deep_link="/next")
    return CardResponse(synthetic=nxt.synthetic, now=nxt.now, kind="step", title=nxt.pick.item.title,
                        when_label=nxt.pick.when_label, line=nxt.pick.why, deep_link="/next")


# ------------------------------------------------------------------------------------------ memory
def list_memory(ctx: SessionCtx) -> MemoryList:
    with conn() as c:
        now = _now(c, ctx)
        s = _student(c, ctx.student_id)
        p = _profile(c, ctx.student_id)
        lang = p.get("language") or "en"
        labels = cf.scoring()["labels"][lang]
        items: list[MemoryItem] = []
        at = p.get("updated_at")
        if p.get("focus_dimension"):
            items.append(MemoryItem(id="profile:focus", kind="focus", statement=f"You chose to grow: {labels[p['focus_dimension']]}",
                                    source=MemorySource(type="you_chose", label="Your choice", at=at),
                                    used_for="Picks steps for this area", learned_at=at))
        from app.services.meta import barriers_config
        bl = barriers_config()["barriers"]
        for b in (p.get("barriers") or []):
            items.append(MemoryItem(id=f"profile:barrier:{b}", kind="barrier", statement=f"What gets in the way: {bl.get(b, {}).get('label', b)}",
                                    source=MemorySource(type="you_chose", label="You tapped this", at=at),
                                    used_for="Favours steps that get around it", learned_at=at))
        for b in (p.get("barriers_from_text") or []):
            items.append(MemoryItem(id=f"profile:barrier_text:{b}", kind="barrier", statement=f"What gets in the way: {bl.get(b, {}).get('label', b)}",
                                    source=MemorySource(type="your_words", label="From what you typed (the text itself is not kept)", at=at),
                                    used_for="Favours steps that get around it", learned_at=at))
        for i, w in enumerate(p.get("free_windows") or []):
            items.append(MemoryItem(id=f"profile:window:{i}", kind="free_window", statement=f"Free: {w}",
                                    source=MemorySource(type="you_chose", label="Your schedule", at=at),
                                    used_for="Only suggests things that fit", learned_at=at))
        for m in c.execute("SELECT * FROM student_memory WHERE student_id = %s ORDER BY updated_at DESC, id DESC", (ctx.student_id,)).fetchall():
            items.append(MemoryItem(id=f"m:{m['id']}", kind=m["kind"], statement=(m["statement_es"] if lang == "es" and m["statement_es"] else m["statement"]),
                                    source=MemorySource(type=m["source_type"], label=m["source_label"], at=m["updated_at"]),
                                    used_for=m["used_for"], learned_at=m["created_at"], last_used_at=m["last_used_at"]))
        return MemoryList(synthetic=bool(s["synthetic"]), now=now, items=items)


def delete_memory(ctx: SessionCtx, memory_id: str | None) -> DeleteResult:
    with conn() as c:
        now = _now(c, ctx)
        n = 0
        if memory_id is None:
            n += c.execute("DELETE FROM student_memory WHERE student_id = %s", (ctx.student_id,)).rowcount
            # declines are memory too: deleting them un-declines
            c.execute("UPDATE recommendations SET status = 'shown' WHERE student_id = %s AND status = 'dismissed'", (ctx.student_id,))
            n += c.execute("""UPDATE profiles SET focus_dimension = NULL, barriers = '{}', barriers_from_text = '{}', free_windows = '{}',
                              social_rung = 1, rung_reason = NULL WHERE student_id = %s""", (ctx.student_id,)).rowcount
        elif memory_id.startswith("m:"):
            row = c.execute("DELETE FROM student_memory WHERE id = %s AND student_id = %s RETURNING kind, key",
                            (int(memory_id[2:]), ctx.student_id)).fetchone()
            if row:
                n = 1
                if row["kind"] == "declined":
                    c.execute("UPDATE recommendations SET status = 'shown' WHERE student_id = %s AND item_id = %s AND status = 'dismissed'",
                              (ctx.student_id, row["key"]))
                if row["kind"] == "rung":
                    c.execute("UPDATE profiles SET social_rung = 1, rung_reason = NULL WHERE student_id = %s", (ctx.student_id,))
        elif memory_id == "profile:focus":
            n = c.execute("UPDATE profiles SET focus_dimension = NULL WHERE student_id = %s", (ctx.student_id,)).rowcount
        elif memory_id.startswith("profile:barrier_text:"):
            b = memory_id.split(":", 2)[2]
            n = c.execute("UPDATE profiles SET barriers_from_text = array_remove(barriers_from_text, %s) WHERE student_id = %s",
                          (b, ctx.student_id)).rowcount
        elif memory_id.startswith("profile:barrier:"):
            b = memory_id.split(":", 2)[2]
            n = c.execute("UPDATE profiles SET barriers = array_remove(barriers, %s) WHERE student_id = %s", (b, ctx.student_id)).rowcount
        elif memory_id.startswith("profile:window:"):
            p = _profile(c, ctx.student_id)
            i = int(memory_id.rsplit(":", 1)[1])
            w = list(p.get("free_windows") or [])
            if 0 <= i < len(w):
                w.pop(i)
                n = c.execute("UPDATE profiles SET free_windows = %s WHERE student_id = %s", (w, ctx.student_id)).rowcount
        if n == 0:
            raise HTTPException(404, detail={"error": "not_found", "message": "Nothing with that id."})
        return DeleteResult(synthetic=True, now=now, deleted=n)


def forget_me(ctx: SessionCtx) -> DeleteResult:
    """Deletes everything personal. Safety events keep only an anonymous count (student id set to null)."""
    with conn() as c:
        now = _now(c, ctx)
        c.execute("UPDATE safety_events SET student_id = NULL WHERE student_id = %s", (ctx.student_id,))
        c.execute("UPDATE wins SET student_id = NULL WHERE student_id = %s", (ctx.student_id,))
        n = c.execute("DELETE FROM students WHERE id = %s", (ctx.student_id,)).rowcount
        return DeleteResult(synthetic=True, now=now, deleted=n)


def inbox(ctx: SessionCtx) -> InboxResponse:
    with conn() as c:
        now = _now(c, ctx)
        rows = c.execute(
            """SELECT id, kind, title, body, deep_link, send_at, delivered FROM notifications
               WHERE student_id = %s AND status IN ('sent','held_budget','opened') ORDER BY send_at DESC LIMIT 30""",
            (ctx.student_id,)).fetchall()
        return InboxResponse(synthetic=True, now=now, items=[
            InboxItem(id=r["id"], kind=r["kind"], title=r["title"], body=r["body"], deep_link=r["deep_link"], at=r["send_at"],
                      delivered="push" if r["delivered"] == "push" else "in_app") for r in rows])
