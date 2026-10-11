"""Offline KB sources loaded at seed time: researched Newark/Camden items and committed snapshots
of live sources (so a fresh seed never depends on a third-party API being up)."""
import json

import psycopg
import yaml

from config.settings import ROOT

SEED = ROOT / "seed"


def research_items(conn: psycopg.Connection) -> int:
    path = SEED / "research" / "nwk_cmd_resources.yaml"
    if not path.exists():
        return 0
    from db.seed import upsert_item
    items = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    for it in items:
        upsert_item(conn, {"source": "research", "attribution": it.get("attribution") or "Compass research (verified)", **it}, tagged_by="staff")
    return len(items)


def snapshot_items(conn: psycopg.Connection) -> int:
    from db.seed import upsert_item
    n = 0
    for path in sorted((SEED / "snapshots").glob("*.json")):
        for it in json.loads(path.read_text(encoding="utf-8")):
            upsert_item(conn, it, tagged_by=it.pop("_tagged_by", "keyword"))
            n += 1
    return n
