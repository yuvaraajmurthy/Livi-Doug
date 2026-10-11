"""Load the demo dataset. Deterministic: same files in, same rows (and ids) out.

  python -m db.seed            # personal/dynamic data + KB (first load)
Called by db.reset for the demo reset button.
"""
import csv
import io
import json
import re
from datetime import date, datetime
from pathlib import Path

import psycopg
import yaml
from psycopg.types.json import Jsonb

from config.settings import CONFIG_DIR, ROOT, get_settings

SQL_DIR = ROOT / "handoff" / "data" / "out" / "sql"
OUT_DIR = ROOT / "handoff" / "data" / "out"
SEED = ROOT / "seed"


def _copy(conn: psycopg.Connection, table: str, cols: list[str], rows_csv: str) -> int:
    with conn.cursor() as cur:
        with cur.copy(f"COPY {table} ({', '.join(cols)}) FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')") as cp:
            cp.write(rows_csv)
        return cur.rowcount


def _csv(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _reshape(path: Path, cols_in: list[str], transform=None) -> str:
    """Re-emit a CSV with only cols_in (optionally transformed per row)."""
    rdr = csv.DictReader(io.StringIO(_csv(path)))
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(cols_in)
    for r in rdr:
        if transform:
            r = transform(r)
        w.writerow([r.get(c, "") for c in cols_in])
    return out.getvalue()


def series_key(title: str) -> str:
    t = re.sub(r"\(.*?\)", "", title.lower())
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:60]


# ----------------------------------------------------------------------------- KB
def load_kb(conn: psycopg.Connection) -> int:
    conn.execute("TRUNCATE kb_tags, kb_items CASCADE")
    cols = ["id", "kind", "title", "campus", "venue", "address", "lat", "lon", "starts_at", "ends_at", "cost",
            "social_level", "solo_friendly", "source", "synthetic"]
    n = _copy(conn, "kb_items", cols, _reshape(SQL_DIR / "kb_items.csv", cols))
    _copy(conn, "kb_tags", ["item_id", "tag_type", "tag", "confidence", "tagged_by"], _csv(SQL_DIR / "kb_tags.csv"))
    _enrich_from_items_json(conn)
    conn.execute("UPDATE kb_items SET series_key = left(regexp_replace(regexp_replace(lower(title), '\\(.*?\\)', '', 'g'), '[^a-z0-9]+', '-', 'g'), 60) WHERE series_key IS NULL")
    conn.execute("UPDATE kb_items SET attribution = 'ScarletWell Wellness Calendar', source_url = coalesce(source_url, 'https://wellnesscalendar.rutgers.edu/') WHERE source = 'wellness_calendar'")
    conn.execute("UPDATE kb_items SET attribution = 'Compass sample event (synthetic)' WHERE synthetic")
    upsert_pins(conn)
    load_micro_steps(conn)
    from ingest.geocode import apply_to_kb
    apply_to_kb(conn, network=False)
    for item_id, campus in (("res-cmd-002", "camden"),):
        conn.execute("INSERT INTO kb_tags (item_id, tag_type, tag, tagged_by) VALUES (%s, 'audience', %s, 'staff') ON CONFLICT DO NOTHING", (item_id, campus))
    for extra in ("research_items", "snapshot_items"):
        from ingest import loaders
        getattr(loaders, extra)(conn)
    return n


def _enrich_from_items_json(conn: psycopg.Connection) -> None:
    data = json.loads((ROOT / "handoff" / "kb" / "items.json").read_text(encoding="utf-8"))
    for it in data["items"]:
        cost_raw = (it.get("cost") or "").lower()
        cost_fix = "unknown" if it.get("type") == "event" and "no cost listed" in cost_raw else None
        conn.execute(
            """UPDATE kb_items SET summary = coalesce(%s, summary), url = coalesce(%s, url), phone = coalesce(%s, phone),
                   address = coalesce(address, %s), hours_text = coalesce(%s, hours_text), all_day = coalesce(%s, all_day),
                   source_url = coalesce(%s, source_url), verified_on = coalesce(verified_on, %s::date),
                   cost = coalesce(%s, cost)
               WHERE id = %s""",
            (it.get("summary") or it.get("access"), it.get("url"), it.get("phone"), it.get("address"), it.get("hours"),
             it.get("all_day"), it.get("url"), it.get("last_checked"), cost_fix, it["id"]),
        )
        if it.get("program"):
            conn.execute("UPDATE kb_items SET summary = coalesce(summary, %s) WHERE id = %s", (it["program"], it["id"]))


def upsert_pins(conn: psycopg.Connection) -> None:
    pins = yaml.safe_load((SEED / "pinned_events.yaml").read_text(encoding="utf-8"))
    for p in pins:
        upsert_item(conn, {**p, "synthetic": True, "demo_pin": True, "source": "synthetic",
                           "attribution": "Compass sample event (synthetic)"}, tagged_by="synthetic")


def upsert_item(conn: psycopg.Connection, p: dict, tagged_by: str = "keyword") -> None:
    conn.execute(
        """INSERT INTO kb_items (id, kind, title, summary, summary_es, campus, venue, address, lat, lon, starts_at, ends_at, cost,
                                 social_level, solo_friendly, url, source, source_url, attribution, synthetic, demo_pin, series_key,
                                 formats, phone, hours_text, open_hours, verified_on, arc_activity_id, all_day, ext_id, modified_at, active)
           VALUES (%(id)s, %(kind)s, %(title)s, %(summary)s, %(summary_es)s, %(campus)s, %(venue)s, %(address)s, %(lat)s, %(lon)s,
                   %(starts_at)s, %(ends_at)s, %(cost)s, %(social_level)s, %(solo_friendly)s, %(url)s, %(source)s, %(source_url)s,
                   %(attribution)s, %(synthetic)s, %(demo_pin)s, %(series_key)s, %(formats)s, %(phone)s, %(hours_text)s,
                   %(open_hours)s, %(verified_on)s, %(arc_activity_id)s, %(all_day)s, %(ext_id)s, %(modified_at)s, true)
           ON CONFLICT (id) DO UPDATE SET
             kind = EXCLUDED.kind, title = EXCLUDED.title, summary = EXCLUDED.summary, summary_es = EXCLUDED.summary_es,
             campus = EXCLUDED.campus, venue = EXCLUDED.venue, address = EXCLUDED.address,
             lat = coalesce(EXCLUDED.lat, kb_items.lat), lon = coalesce(EXCLUDED.lon, kb_items.lon),
             starts_at = EXCLUDED.starts_at, ends_at = EXCLUDED.ends_at, cost = EXCLUDED.cost, social_level = EXCLUDED.social_level,
             solo_friendly = EXCLUDED.solo_friendly, url = EXCLUDED.url, source_url = EXCLUDED.source_url,
             attribution = EXCLUDED.attribution, synthetic = EXCLUDED.synthetic, demo_pin = EXCLUDED.demo_pin,
             series_key = EXCLUDED.series_key, formats = EXCLUDED.formats, phone = EXCLUDED.phone, hours_text = EXCLUDED.hours_text,
             open_hours = EXCLUDED.open_hours, verified_on = EXCLUDED.verified_on, arc_activity_id = EXCLUDED.arc_activity_id,
             all_day = EXCLUDED.all_day, ext_id = EXCLUDED.ext_id, modified_at = EXCLUDED.modified_at, active = true,
             updated_at = now()""",
        {
            "id": p["id"], "kind": p.get("kind", "event"), "title": p["title"], "summary": p.get("summary"),
            "summary_es": p.get("summary_es"), "campus": p.get("campus", "online"), "venue": p.get("venue"),
            "address": p.get("address"), "lat": p.get("lat"), "lon": p.get("lon"), "starts_at": p.get("starts_at"),
            "ends_at": p.get("ends_at"), "cost": p.get("cost", "unknown"), "social_level": p.get("social_level"),
            "solo_friendly": p.get("solo_friendly"), "url": p.get("url"), "source": p.get("source", "research"),
            "source_url": p.get("source_url") or p.get("url"), "attribution": p.get("attribution"),
            "synthetic": bool(p.get("synthetic", False)), "demo_pin": bool(p.get("demo_pin", False)),
            "series_key": p.get("series_key") or series_key(p["title"]), "formats": p.get("formats") or [],
            "phone": p.get("phone"), "hours_text": p.get("hours_text"),
            "open_hours": Jsonb(p["open_hours"]) if p.get("open_hours") else None,
            "verified_on": p.get("verified_on"), "arc_activity_id": p.get("arc_activity_id"),
            "all_day": bool(p.get("all_day", False)), "ext_id": p.get("ext_id"), "modified_at": p.get("modified_at"),
        },
    )
    if any(k in p for k in ("dimensions", "causes", "barriers", "formats")):
        conn.execute("DELETE FROM kb_tags WHERE item_id = %s AND tagged_by <> 'staff'", (p["id"],))
        for tag_type, key in (("dimension", "dimensions"), ("cause", "causes"), ("barrier", "barriers"), ("format", "formats")):
            for t in p.get(key) or []:
                conf = (p.get("confidence") or {}).get(t, 1.0) if isinstance(p.get("confidence"), dict) else 1.0
                conn.execute(
                    "INSERT INTO kb_tags (item_id, tag_type, tag, confidence, tagged_by) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    (p["id"], tag_type, t, conf, tagged_by))


def load_micro_steps(conn: psycopg.Connection) -> None:
    for m in yaml.safe_load((CONFIG_DIR / "micro_steps.yaml").read_text(encoding="utf-8")):
        upsert_item(conn, {"id": m["id"], "kind": "micro", "title": m["title"], "summary_es": m.get("title_es"),
                           "campus": "online", "cost": "free", "social_level": 1, "solo_friendly": True,
                           "source": "compass", "attribution": "Compass micro-steps", "formats": m.get("formats", []),
                           "dimensions": [m["dimension"]]}, tagged_by="staff")


# ----------------------------------------------------------------------------- people and history
PERSONAL_TABLES = [
    "students", "challenges", "crisis_lines", "app_clock", "wording_queue",
]


def load_people(conn: psycopg.Connection) -> None:
    subs = conn.execute("SELECT student_id, endpoint, p256dh, auth FROM push_subscriptions WHERE revoked_at IS NULL").fetchall()
    conn.execute("TRUNCATE students, challenges, crisis_lines, app_clock, wording_queue, safety_events RESTART IDENTITY CASCADE")
    _copy(conn, "students", ["id", "campus", "level", "class_year", "housing", "first_gen", "works_20plus_hours", "school",
                             "home_area", "language", "synthetic"], _csv(SQL_DIR / "students.csv"))
    _copy(conn, "inventory_takes", ["id", "student_id", "take_no", "taken_on", "source", "total"], _csv(SQL_DIR / "inventory_takes.csv"))
    conn.execute("SELECT setval('inventory_takes_id_seq', (SELECT max(id) FROM inventory_takes))")
    _copy(conn, "dimension_scores", ["take_id", "dimension", "score"], _csv(SQL_DIR / "dimension_scores.csv"))
    _copy(conn, "recommendations", ["id", "student_id", "item_id", "dimension", "shown_on", "status"], _csv(SQL_DIR / "recommendations.csv"))
    conn.execute("SELECT setval('recommendations_id_seq', (SELECT max(id) FROM recommendations))")
    _copy(conn, "commitments", ["id", "recommendation_id", "student_id", "item_id", "with_friend", "status"], _csv(SQL_DIR / "commitments.csv"))
    conn.execute("SELECT setval('commitments_id_seq', (SELECT max(id) FROM commitments))")
    conn.execute("CREATE TEMP TABLE inv_stage (commitment_id bigint, token text, accepted boolean) ON COMMIT DROP")
    _copy(conn, "inv_stage", ["commitment_id", "token", "accepted"], _csv(SQL_DIR / "invites.csv"))
    conn.execute("INSERT INTO invites (commitment_id, token, accepted_at) SELECT commitment_id, token, CASE WHEN accepted THEN '2026-09-30'::timestamptz END FROM inv_stage")
    _copy(conn, "feedback", ["commitment_id", "student_id", "went", "helped"], _csv(SQL_DIR / "feedback.csv"))
    conn.execute("UPDATE feedback SET created_at = '2026-09-30'")
    conn.execute("INSERT INTO arc_credits (commitment_id, status) SELECT commitment_id, 'mock' FROM feedback WHERE went")
    _copy(conn, "wins", ["id", "campus", "dimension", "text", "status", "same_here"], _csv(SQL_DIR / "wins.csv"))
    conn.execute("UPDATE wins SET synthetic = true, created_at = '2026-10-09 12:00-04'")

    for c in yaml.safe_load((SEED / "challenges.yaml").read_text(encoding="utf-8")):
        conn.execute(
            """INSERT INTO challenges (id, title, scope, scope_value, scope_label, dimension, starts_on, ends_on, goal_steps,
                                       base_progress, group_size, rule, synthetic)
               VALUES (%(id)s, %(title)s, %(scope)s, %(scope_value)s, %(scope_label)s, %(dimension)s, %(starts_on)s, %(ends_on)s,
                       %(goal_steps)s, %(base_progress)s, %(group_size)s, %(rule)s, true)""",
            {"dimension": None, **c})
    for line in yaml.safe_load((SEED / "crisis_lines.yaml").read_text(encoding="utf-8")):
        conn.execute(
            """INSERT INTO crisis_lines (campus, name, kind, contact, href, hours, language, sort, source_url)
               VALUES (%(campus)s, %(name)s, %(kind)s, %(contact)s, %(href)s, %(hours)s, %(language)s, %(sort)s, %(source_url)s)""",
            {"href": None, "source_url": None, **line})
    for sid, prof in yaml.safe_load((SEED / "persona_profiles.yaml").read_text(encoding="utf-8")).items():
        conn.execute("INSERT INTO profiles (student_id, free_windows, language, free_only) VALUES (%s, %s, %s, %s)",
                     (sid, prof["free_windows"], prof["language"], prof["free_only"]))
    conn.execute("INSERT INTO app_clock (id, sim_now) VALUES (1, %s)", (datetime.fromisoformat(get_settings().default_now),))
    seed_demo_history(conn)
    for s in subs:
        conn.execute("INSERT INTO push_subscriptions (student_id, endpoint, p256dh, auth) VALUES (%s, %s, %s, %s) ON CONFLICT (endpoint) DO NOTHING",
                     (s["student_id"], s["endpoint"], s["p256dh"], s["auth"]))


HISTORY = [
    # series, campus, past instances (date, start, end), attendees, helped>=4, going for the pinned instance, pinned id
    ("commuter-lunch-games-newark", "newark", ["2026-09-22", "2026-09-29", "2026-10-06"], 36, 26, 14, "pin-andre-lunch-2026-10-13"),
    ("pickup-basketball-newark", "newark", ["2026-10-01", "2026-10-08"], 20, 13, 6, "pin-andre-basketball-2026-10-22"),
    ("livingston-game-night", "new_brunswick", ["2026-09-30", "2026-10-07"], 24, 17, 7, "pin-jordan-hall-game-night-2026-10-14"),
]


def seed_demo_history(conn: psycopg.Connection) -> None:
    """Deterministic, synthetic history for pinned series: past ratings (for 'helped similar students')
    and planned commitments (for 'N students are going'). All rows belong to synthetic students."""
    for series, campus, dates, attendees, helped, going, pin_id in HISTORY:
        pin = conn.execute("SELECT * FROM kb_items WHERE id = %s", (pin_id,)).fetchone()
        if not pin:
            continue
        housing_filter = "AND housing = 'commuter'" if campus == "newark" else "AND housing = 'resident'"
        pool = [r["id"] for r in conn.execute(
            f"SELECT id FROM students WHERE campus = %s AND synthetic AND id NOT LIKE 'DEMO-%%' {housing_filter} ORDER BY id LIMIT %s",
            (campus, attendees + going)).fetchall()]
        hist_ids = []
        for d in dates:
            hid = f"hist-{series}-{d}"
            hist_ids.append(hid)
            conn.execute(
                """INSERT INTO kb_items (id, kind, title, campus, venue, address, lat, lon, starts_at, ends_at, cost, social_level,
                                         solo_friendly, source, synthetic, series_key, formats, active, attribution)
                   VALUES (%s, 'event', %s, %s, %s, %s, %s, %s, %s::date + %s::time, %s::date + %s::time, 'free', %s, true,
                           'synthetic', true, %s, %s, false, 'Compass sample event (synthetic)')
                   ON CONFLICT (id) DO NOTHING""",
                (hid, pin["title"], campus, pin["venue"], pin["address"], pin["lat"], pin["lon"], d, pin["starts_at"].time(),
                 d, pin["ends_at"].time(), pin["social_level"], series, pin["formats"]))
        for i, sid in enumerate(pool[:attendees]):
            hid = hist_ids[i % len(hist_ids)]
            rid = conn.execute(
                "INSERT INTO recommendations (student_id, item_id, dimension, shown_on, status) VALUES (%s, %s, 'social', %s::date - 3, 'committed') RETURNING id",
                (sid, hid, hid[-10:])).fetchone()["id"]
            cid = conn.execute(
                "INSERT INTO commitments (recommendation_id, student_id, item_id, with_friend, status) VALUES (%s, %s, %s, %s, 'went') RETURNING id",
                (rid, sid, hid, i % 4 == 0)).fetchone()["id"]
            conn.execute("INSERT INTO feedback (commitment_id, student_id, went, helped, created_at) VALUES (%s, %s, true, %s, %s::date)",
                         (cid, sid, 4 + (i % 2) if i < helped else 2 + (i % 2), hid[-10:]))
        for sid in pool[attendees:attendees + going]:
            rid = conn.execute(
                "INSERT INTO recommendations (student_id, item_id, dimension, shown_on, status) VALUES (%s, %s, 'social', '2026-10-11', 'committed') RETURNING id",
                (sid, pin_id)).fetchone()["id"]
            conn.execute("INSERT INTO commitments (recommendation_id, student_id, item_id, status) VALUES (%s, %s, %s, 'planned')",
                         (rid, sid, pin_id))


def seed_all(conn: psycopg.Connection, kb: bool = True) -> None:
    with conn.transaction():
        if kb:
            load_kb(conn)
        else:
            upsert_pins(conn)
        load_people(conn)


if __name__ == "__main__":
    import sys
    from app.db import connect_direct
    with connect_direct() as c:
        seed_all(c, kb="--no-kb" not in sys.argv)
        c.commit()
        for t in ("students", "inventory_takes", "kb_items", "recommendations", "commitments", "feedback", "challenges", "crisis_lines"):
            print(t, c.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"])
