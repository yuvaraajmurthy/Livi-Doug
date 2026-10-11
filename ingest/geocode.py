"""Geocoding with a per-address cache. Amazon Location (Places v2) when available, else OpenStreetMap Nominatim
at 1 request/second with an identifying User-Agent. Results are also committed to seed/geocodes.json so a
fresh seed never needs the network.

  python -m ingest.geocode          # geocode every KB address missing coordinates, update seed/geocodes.json
"""
import json
import re
import time
import urllib.parse
import urllib.request

from config.settings import ROOT

UA = "CompassHackathon/1.0 (Rutgers Health Hack 2026 student prototype; contact via ScarletWell)"
SEED_FILE = ROOT / "seed" / "geocodes.json"
_last = [0.0]


def clean_address(addr: str) -> str:
    a = re.sub(r",?\s*(Room|Suite|Rm\.?|Floor)\s*[\w-]+", "", addr or "", flags=re.I)
    a = re.sub(r"\s+", " ", a).strip(" ,")
    return a


def nominatim(addr: str) -> tuple[float, float] | None:
    wait = 1.1 - (time.monotonic() - _last[0])
    if wait > 0:
        time.sleep(wait)
    q = urllib.parse.urlencode({"q": addr, "format": "json", "limit": 1, "countrycodes": "us"})
    req = urllib.request.Request(f"https://nominatim.openstreetmap.org/search?{q}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
    finally:
        _last[0] = time.monotonic()
    if not data:
        return None
    return float(data[0]["lat"]), float(data[0]["lon"])


def amazon_location(addr: str) -> tuple[float, float] | None:
    try:
        import boto3
        c = boto3.client("geo-places", region_name="us-west-2")
        r = c.geocode(QueryText=addr, MaxResults=1, Filter={"IncludeCountries": ["USA"]})
        items = r.get("ResultItems") or []
        if not items:
            return None
        lon, lat = items[0]["Position"]
        return float(lat), float(lon)
    except Exception:
        return None


def load_seed() -> dict:
    return json.loads(SEED_FILE.read_text(encoding="utf-8")) if SEED_FILE.exists() else {}


def geocode(conn, addr: str, prefer: str = "amazon", network: bool = True) -> tuple[float, float] | None:
    key = clean_address(addr)
    if not key:
        return None
    hit = conn.execute("SELECT lat, lon FROM geocode_cache WHERE address = %s", (key,)).fetchone()
    if hit:
        return (hit["lat"], hit["lon"]) if hit["lat"] is not None else None
    seed = load_seed().get(key)
    if seed:
        res, provider = (seed["lat"], seed["lon"]), seed.get("provider", "seed")
    elif not network:
        return None
    else:
        res, provider = None, "none"
        if prefer == "amazon":
            res, provider = amazon_location(key), "amazon_location"
        if res is None:
            res, provider = nominatim(key), "nominatim"
    conn.execute("INSERT INTO geocode_cache (address, lat, lon, provider) VALUES (%s, %s, %s, %s) ON CONFLICT (address) DO NOTHING",
                 (key, res[0] if res else None, res[1] if res else None, provider))
    return res


def apply_to_kb(conn, prefer: str = "amazon", network: bool = True) -> dict:
    rows = conn.execute("SELECT id, address, campus FROM kb_items WHERE lat IS NULL AND address IS NOT NULL AND address <> '' AND campus <> 'online'").fetchall()
    stats = {"tried": 0, "found": 0}
    for r in rows:
        stats["tried"] += 1
        addr = r["address"]
        if "NJ" not in addr:
            addr += {"newark": ", Newark, NJ", "camden": ", Camden, NJ"}.get(r["campus"], ", NJ")
        res = geocode(conn, addr, prefer, network)
        if res:
            stats["found"] += 1
            conn.execute("UPDATE kb_items SET lat = %s, lon = %s WHERE id = %s", (res[0], res[1], r["id"]))
    return stats


def export_seed(conn) -> int:
    rows = conn.execute("SELECT address, lat, lon, provider FROM geocode_cache WHERE lat IS NOT NULL ORDER BY address").fetchall()
    data = {r["address"]: {"lat": round(r["lat"], 6), "lon": round(r["lon"], 6), "provider": r["provider"]} for r in rows}
    SEED_FILE.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return len(data)


if __name__ == "__main__":
    from app.db import connect_direct
    with connect_direct() as c:
        print(apply_to_kb(c))
        c.commit()
        print("seed entries:", export_seed(c))
