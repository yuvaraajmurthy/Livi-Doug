"""Scarlet Sync: a student-built public API that aggregates Rutgers events. We read its public data only
(no code reused), at most hourly, and snapshot it so the demo never depends on it being up.

Kept: recreation, getinvolved (club events), newbrunswick, mason_gross, imleagues (collapsed to "join an
intramural team" resources), libcal (collapsed to one study-space place per library, no invented hours).
Dropped: athletics (mostly away games)."""
import json
import re
import urllib.request

BASE = "https://scarlet-sync-backend-1086246455189.us-east1.run.app"
UA = "CompassHackathon/1.0 (Rutgers Health Hack 2026 student prototype)"
ATTR = "via Scarlet Sync (student project)"

LIBRARIES = {
    "Alexander Library": ("new_brunswick", "169 College Ave, New Brunswick, NJ 08901"),
    "Dana Library (Newark)": ("newark", "185 University Ave, Newark, NJ 07102"),
    "Robeson Library (Camden)": ("camden", "300 N 4th St, Camden, NJ 08102"),
    "Carr Library": ("new_brunswick", "75 Avenue E, Piscataway, NJ 08854"),
    "Kilmer Library": ("new_brunswick", "75 Avenue E, Piscataway, NJ 08854"),
    "Douglass Library": ("new_brunswick", "8 Chapel Dr, New Brunswick, NJ 08901"),
    "Math/Physics Library": ("new_brunswick", "110 Frelinghuysen Rd, Piscataway, NJ 08854"),
    "Library of Science and Medicine (LSM)": ("new_brunswick", "165 Bevier Rd, Piscataway, NJ 08854"),
    "Chang Science Library": ("new_brunswick", "59 Dudley Rd, New Brunswick, NJ 08901"),
    "Art Library": ("new_brunswick", "71 Hamilton St, New Brunswick, NJ 08901"),
}
KNOWN_VENUES = {
    "livingston student center": ("new_brunswick", "84 Joyce Kilmer Ave, Piscataway, NJ 08854"),
    "livingstone student center": ("new_brunswick", "84 Joyce Kilmer Ave, Piscataway, NJ 08854"),
    "rutgers club": ("new_brunswick", "199 College Ave, New Brunswick, NJ 08901"),
    "the yard": ("new_brunswick", "40 College Ave, New Brunswick, NJ 08901"),
    "zimmerli art museum": ("new_brunswick", "71 Hamilton St, New Brunswick, NJ 08901"),
    "casc": ("new_brunswick", "126 College Ave, New Brunswick, NJ 08901"),
    "busch student center": ("new_brunswick", "604 Bartholomew Rd, Piscataway, NJ 08854"),
}


def fetch_all() -> list[dict]:
    out = []
    for off in range(0, 2000, 100):
        req = urllib.request.Request(f"{BASE}/events?limit=100&offset={off}", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        out += d.get("events", [])
        if len(d.get("events", [])) < 100:
            break
    return out


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50]


def _venue(loc: str | None) -> tuple[str, str | None]:
    if not loc:
        return "new_brunswick", None
    low = loc.lower()
    if low.strip() == "online":
        return "online", None
    for k, (campus, addr) in KNOWN_VENUES.items():
        if low.startswith(k) or k in low:
            return campus, addr
    if "newark" in low:
        return "newark", None
    if "camden" in low:
        return "camden", None
    return "new_brunswick", None


def to_items(events: list[dict]) -> list[dict]:
    items: dict[str, dict] = {}
    for e in events:
        src = e.get("source")
        url = e.get("source_url") or ""
        if src == "athletics" or not url.startswith("http"):
            continue
        if src == "libcal":
            lib = e.get("location") or ""
            campus, addr = LIBRARIES.get(lib, ("new_brunswick", None))
            iid = f"place-libcal-{_slug(lib)}"
            items.setdefault(iid, {
                "id": iid, "kind": "place", "title": f"Study space at {lib.replace(' (Newark)', '').replace(' (Camden)', '')}",
                "summary": "Bookable study rooms and open seating. Check live room availability on LibCal.",
                "campus": campus, "venue": lib, "address": addr, "cost": "free", "url": "https://libcal.rutgers.edu/spaces",
                "source": "scarlet_sync:libcal", "source_url": "https://libcal.rutgers.edu/spaces", "attribution": ATTR,
                "hours_text": "Room availability shown live on LibCal", "social_level": 1, "solo_friendly": True,
                "formats": ["quiet", "drop_in"], "dimensions": ["intellectual"], "causes": ["academic_workload"],
            })
            continue
        if src == "imleagues":
            loc = e.get("location") or ""
            sport = "Pickleball" if "pickleball" in loc.lower() else "Field sports"
            where = "Livingston Rec Center" if "livingston" in loc.lower() else ("University Park fields (Busch)" if "university park" in loc.lower() else loc)
            iid = f"res-imleagues-{_slug(sport + '-' + where)}"
            items.setdefault(iid, {
                "id": iid, "kind": "resource", "title": f"Join an intramural team: {sport.lower()} at {where}",
                "summary": "Rutgers Recreation intramural leagues. Sign up solo as a free agent and get placed on a team.",
                "campus": "new_brunswick", "venue": where,
                "address": "62 Road 3, Piscataway, NJ 08854" if "Livingston" in where else "University Park, Piscataway, NJ 08854",
                "cost": "free", "url": "https://www.imleagues.com/spa/portal/school?schoolId=rutgers", "source": "scarlet_sync:imleagues",
                "source_url": url, "attribution": ATTR, "social_level": 3, "solo_friendly": True,
                "formats": ["sports", "games", "active", "structured"], "dimensions": ["physical", "social"], "causes": ["inactivity", "loneliness"],
            })
            continue
        campus, addr = _venue(e.get("location"))
        start, end = e.get("start_time"), e.get("end_time")
        iid = f"ss-{src}-{(e.get('id') or '')[:12]}"
        items[iid] = {
            "id": iid, "kind": "event", "title": e.get("title") or "Event", "summary": (f"Hosted by {e['host']}." if e.get("host") else None),
            "campus": campus, "venue": e.get("location") if e.get("location") not in (None, "To be announced", "Online") else None,
            "address": addr, "starts_at": start, "ends_at": end, "cost": "free" if e.get("is_free") else "unknown", "url": url,
            "source": f"scarlet_sync:{src}", "source_url": url, "attribution": ATTR + (f"; {e['host']}" if e.get("host") else ""),
            "ext_id": e.get("id"),
        }
    return list(items.values())


def ingest(conn, snapshot_path=None) -> dict:
    from db.seed import upsert_item
    events = fetch_all()
    items = to_items(events)
    for it in items:
        upsert_item(conn, it, tagged_by="keyword")
    if snapshot_path:
        snapshot_path.write_text(json.dumps(items, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return {"fetched": len(events), "upserted": len(items)}
