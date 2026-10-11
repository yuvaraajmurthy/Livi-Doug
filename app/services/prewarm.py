"""Pre-generate and cache AI wording ("why" lines and if-then plans) for the demo personas' scripted inputs, so the
demo shows AI wording without ever waiting on a model. Runs after reset (background) and from the CLI."""
import logging
import threading
from dataclasses import replace
from datetime import datetime

from app.clock import NY
from app.db import conn
from app.engine import care_first as cf
from app.engine.rank import cfg as engine_cfg, rank
from app.llm import queue, wording
from app.repo import kb
from app.services import present

log = logging.getLogger("compass.prewarm")

SCRIPT = [
    # student, focus, barriers, target rung, simulated time
    ("DEMO-ANDRE", "social", ("no_time", "dont_know_anyone"), 2, "2026-10-12T09:00"),
    ("DEMO-ANDRE", "social", ("no_time", "dont_know_anyone"), 3, "2026-10-19T09:00"),
    ("DEMO-PRIYA", "physical", ("coursework",), 1, "2026-10-12T09:00"),
    ("DEMO-TAYLOR", None, (), 1, "2026-10-12T09:00"),
    ("DEMO-SOFIA", "financial", ("no_time", "money"), 1, "2026-10-12T09:00"),
    ("DEMO-JORDAN", "social", ("dont_know_anyone", "not_my_scene"), 2, "2026-10-12T09:00"),
]


def enqueue_all() -> int:
    from app.services.loop import _plan_facts
    n = 0
    with conn() as c:
        for sid, focus, barriers, rung, when in SCRIPT:
            now = datetime.fromisoformat(when).replace(tzinfo=NY)
            scores, _ = kb.latest_scores(c, sid, now)
            ctx = kb.student_ctx(c, sid, now, cf.applies(scores))
            ctx = replace(ctx, focus=focus or min(scores, key=scores.get), barriers=barriers, target_rung=rung, declined=frozenset(), committed=frozenset())
            res = rank(ctx, kb.load_items(c, ctx.campus, now, engine_cfg()["horizon_days"]), kb.helped_stats(c, ctx, now), [], now)
            p = c.execute("SELECT free_windows FROM profiles WHERE student_id = %s", (sid,)).fetchone() or {}
            for s in res.picks:
                wording.get(c, "why", present.why_facts(s, ctx), ctx.language)
                wording.get(c, "plan", _plan_facts(s.item, p.get("free_windows") or []), ctx.language)
                n += 2
    return n


def run(drain: bool = True) -> dict:
    n = enqueue_all()
    done = queue.drain(max_rounds=30) if drain else 0
    log.info("prewarm", extra={"outcome": f"enqueued={n} generated={done}"})
    return {"enqueued": n, "generated": done}


def run_in_background() -> None:
    threading.Thread(target=lambda: _safe(run), name="prewarm", daemon=True).start()


def _safe(fn) -> None:
    try:
        fn()
    except Exception as exc:
        log.warning("prewarm failed", extra={"err": type(exc).__name__})
