"""ScarletWell Wellness Calendar (WordPress "The Events Calendar" REST API). Public, read-only, no key.

Polite: hourly at most, identifying User-Agent, pages via next_rest_url, incremental on `modified`.
Blank cost means unknown, not free. Venues have addresses but no coordinates (geocoded later)."""
import html
import json
import re
import urllib.request
from datetime import datetime

API = "https://wellnesscalendar.rutgers.edu/wp-json/tribe/events/v1/events"
UA = "Mozilla/5.0 (compatible; CompassHackathon/1.0; Rutgers Health Hack 2026 student prototype)"
CAT2DIM = {"Art/Music": ["intellectual", "social"], "Emotional/Mental Health": ["emotional"], "Environment/Nature": ["environmental"],
           "Physical/Movement": ["physical"], "Wellness Week": [], "Other": []}


def clean(s: str | None) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def fetch(start: str, max_pages: int = 10) -> list[dict]:
    url = f"{API}?per_page=50&start_date={start}"
    out = []
    for _ in range(max_pages):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        out += d.get("events", [])
        url = d.get("next_rest_url")
        if not url:
            break
    return out


def campus_of(e: dict) -> str:
    if e.get("is_virtual"):
        return "online"
    v = e.get("venue") if isinstance(e.get("venue"), dict) else {}
    city = (v.get("city") or "").strip().lower()
    if city == "newark":
        return "newark"
    if city == "camden":
        return "camden"
    return "new_brunswick"


def cost_of(raw: str | None) -> str:
    c = clean(raw).lower()
    if not c:
        return "unknown"
    if "free" in c and "$" not in c:
        return "free"
    return "paid" if re.search(r"\$\s?\d", c) else "unknown"


def to_item(e: dict) -> dict:
    v = e.get("venue") if isinstance(e.get("venue"), dict) else {}
    cats = [c["name"] for c in e.get("categories", [])]
    addr = ", ".join(x for x in [v.get("address"), v.get("city"), "NJ" if v.get("city") else None] if x) or None
    return {
        "id": f"evt-{e['id']}-{e['start_date'][:10]}", "kind": "event", "title": clean(e["title"]),
        "summary": clean(e.get("description"))[:600] or None, "campus": campus_of(e), "venue": clean(v.get("venue")) or None,
        "address": addr, "starts_at": e.get("start_date"), "ends_at": e.get("end_date"), "all_day": bool(e.get("all_day")),
        "cost": cost_of(e.get("cost")), "url": e.get("url"), "source": "wellness_calendar",
        "source_url": e.get("url"), "attribution": "ScarletWell Wellness Calendar", "ext_id": str(e["id"]),
        "modified_at": datetime.fromisoformat(e["modified_utc"] + "+00:00") if e.get("modified_utc") else None,
        "dimensions": sorted({d for c in cats for d in CAT2DIM.get(c, [])}),
        "verified_on": (e.get("modified") or "")[:10] or None,
    }


def ingest(conn, start: str) -> dict:
    from db.seed import upsert_item
    stats = {"fetched": 0, "upserted": 0, "skipped": 0}
    for e in fetch(start):
        stats["fetched"] += 1
        it = to_item(e)
        cur = conn.execute("SELECT modified_at FROM kb_items WHERE id = %s", (it["id"],)).fetchone()
        if cur and cur["modified_at"] and it["modified_at"] and cur["modified_at"] >= it["modified_at"]:
            stats["skipped"] += 1
            continue
        if not it["dimensions"]:
            it.pop("dimensions")  # keep existing tags until the tagger runs
        upsert_item(conn, it, tagged_by="keyword")
        conn.execute("UPDATE kb_items SET updated_at = now() WHERE id = %s", (it["id"],))
        stats["upserted"] += 1
    return stats
