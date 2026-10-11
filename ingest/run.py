"""Hourly ingestion (EventBridge Scheduler -> ECS RunTask `python -m app.cli ingest`).

Each source is isolated: one failing never stops the others. Every run is recorded in ingest_runs.
  python -m ingest.run [--snapshot]   # --snapshot also refreshes seed/snapshots/*.json for offline seeding
"""
import sys
import traceback
from datetime import datetime

from app.clock import NY
from app.db import connect_direct
from config.settings import ROOT


def _run(conn, source: str, fn) -> dict:
    rid = conn.execute("INSERT INTO ingest_runs (source) VALUES (%s) RETURNING id", (source,)).fetchone()["id"]
    conn.commit()
    try:
        stats = fn()
        conn.execute("UPDATE ingest_runs SET finished_at = now(), fetched = %s, upserted = %s, skipped = %s, failed = 0 WHERE id = %s",
                     (stats.get("fetched") or stats.get("candidates"), stats.get("upserted") or stats.get("tagged") or stats.get("found"),
                      stats.get("skipped"), rid))
        conn.commit()
        print(source, stats, flush=True)
        return stats
    except Exception as exc:
        conn.rollback()
        conn.execute("UPDATE ingest_runs SET finished_at = now(), failed = 1, note = %s WHERE id = %s", (type(exc).__name__, rid))
        conn.commit()
        print(source, "FAILED", type(exc).__name__, flush=True)
        traceback.print_exc()
        return {}


def run_all(snapshot: bool = False) -> None:
    from ingest import calendar, geocode, scarlet_sync, tagger
    snap = ROOT / "seed" / "snapshots"
    snap.mkdir(parents=True, exist_ok=True)
    today = datetime.now(NY).date().isoformat()
    with connect_direct() as c:
        _run(c, "wellness_calendar", lambda: calendar.ingest(c, today))
        _run(c, "scarlet_sync", lambda: scarlet_sync.ingest(c, snap / "scarlet_sync.json" if snapshot else None))
        _run(c, "geocode", lambda: geocode.apply_to_kb(c))
        _run(c, "ai_tagging", lambda: tagger.tag_pending(c))
        if snapshot:
            geocode.export_seed(c)
            export_tags(c)


def export_tags(c) -> None:
    """Persist AI tags for offline seeding, so a fresh seed has the same tags without calling a model."""
    import json
    rows = c.execute("SELECT item_id, tag_type, tag, confidence FROM kb_tags WHERE tagged_by = 'ai' ORDER BY 1, 2, 3").fetchall()
    meta = c.execute("SELECT id, social_level, solo_friendly, formats FROM kb_items WHERE id IN (SELECT DISTINCT item_id FROM kb_tags WHERE tagged_by = 'ai')").fetchall()
    out = {"tags": [dict(r, confidence=float(r["confidence"])) for r in rows], "items": [dict(m) for m in meta]}
    (ROOT / "seed" / "ai_tags.json").write_text(json.dumps(out, indent=0, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    run_all(snapshot="--snapshot" in sys.argv)
