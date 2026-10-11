"""Debug helper: python -m scripts.try_engine andre social no_time,dont_know_anyone 2026-10-12T09:00 [rung]"""
import sys
from dataclasses import replace
from datetime import datetime

from app.clock import NY
from app.db import connect_direct
from app.engine.care_first import applies
from app.engine.rank import rank
from app.repo import kb

persona, focus, barriers, when = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
rung = int(sys.argv[5]) if len(sys.argv) > 5 else None
sid = "DEMO-" + persona.upper()
now = datetime.fromisoformat(when).replace(tzinfo=NY)
with connect_direct() as c:
    scores, _ = kb.latest_scores(c, sid, now)
    ctx = kb.student_ctx(c, sid, now, applies(scores))
    ctx = replace(ctx, focus=focus, barriers=tuple(b for b in barriers.split(",") if b), target_rung=rung or (2 if "dont_know_anyone" in barriers else 1))
    items = kb.load_items(c, ctx.campus, now)
    stats = kb.helped_stats(c, ctx, now)
    r = rank(ctx, items, stats, kb.memory_facts(c, sid), now)
print("care_first", r.care_first, "considered", r.considered, "prior", stats.prior)
for s in r.picks:
    print(f"{s.score:.3f} {s.item.id[:40]:40s} {s.item.title[:42]:42s} {s.item.starts_at} walk={s.walk_min} {s.window_label}")
    print("      ", {k: round(v, 2) for k, v in s.components.items()}, s.component_text.get("helped_similar"), [f[0] for f in s.filters])
