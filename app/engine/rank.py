"""Next-step engine: hard filters -> fit score -> memory adjustment -> distance -> diverse top 3.

Pure: no I/O, no clock reads, no randomness unless explore is on (then seeded). Same inputs, same output.
"""
import hashlib
import math
import random
import re
from datetime import datetime, time, timedelta
from functools import lru_cache

import yaml

from app.engine.types import HelpedStats, KbItem, MemoryFact, RankResult, Scored, StudentCtx, Window
from app.services.meta import barriers_config
from config.settings import CONFIG_DIR

DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_WIN = re.compile(r"^\s*(mon|tue|wed|thu|fri|sat|sun)\w*\s+(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$", re.I)


@lru_cache
def cfg() -> dict:
    return yaml.safe_load((CONFIG_DIR / "engine.yaml").read_text(encoding="utf-8"))


def parse_window(label: str) -> Window | None:
    m = _WIN.match(label or "")
    if not m:
        return None
    d, h1, m1, h2, m2 = m.groups()
    return Window(DAYS[d.lower()[:3]], time(int(h1), int(m1)), time(int(h2), int(m2)), label.strip())


def _fmt_time(t: time) -> str:
    h = t.hour % 12 or 12
    return f"{h}:{t.minute:02d}" if t.minute else f"{h}"


def window_phrase(w: Window) -> str:
    return f"your {DAY_NAMES[w.weekday]} gap, {_fmt_time(w.start)}–{_fmt_time(w.end)}"


# --------------------------------------------------------------------------- geometry
def walk_minutes(ctx: StudentCtx, item: KbItem) -> int | None:
    if item.campus == "online" or item.lat is None or item.lon is None:
        return None
    anchors = cfg()["campus_anchors"]
    a = anchors.get(ctx.home_area or "") or anchors.get(ctx.campus)
    if not a:
        return None
    r = 6371.0
    p1, p2 = math.radians(a["lat"]), math.radians(item.lat)
    dphi, dl = p2 - p1, math.radians(item.lon - a["lon"])
    km = 2 * r * math.asin(math.sqrt(math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2))
    d = cfg()["distance"]
    return max(1, round(km * 1000 * d["detour_factor"] / d["walk_m_per_min"]))


# --------------------------------------------------------------------------- windows
def _minutes(a: datetime, b: datetime) -> float:
    return (b - a).total_seconds() / 60


def window_fit(ctx: StudentCtx, item: KbItem, now: datetime, walk: int | None) -> tuple[float, str | None, bool]:
    """(score, label, passes_filter). Label like 'Fits your Tuesday gap, 12:20–2:30'."""
    c = cfg()
    if item.kind == "micro":
        return 1.0, "Any time", True
    if item.starts_at is None:  # resource / place / online service
        if item.campus == "online" or item.kind == "online":
            return c["online_anytime_score"], "Any time, online", True
        if item.open_hours and ctx.windows:
            for w in ctx.windows:
                day = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][w.weekday]
                for o, e in item.open_hours.get(day, []):
                    if time.fromisoformat(o) < w.end and time.fromisoformat(e) > w.start:
                        return c["open_place_score"], f"Open during {window_phrase(w)}", True
            return 0.2, None, True
        return (c["unknown_hours_score"], None, True)
    start, end = item.starts_at, item.ends_at or (item.starts_at + timedelta(hours=1))
    dur = _minutes(start, end)
    if item.all_day or dur >= c["long_event_minutes"]:
        need_len = c["drop_in_minutes"]
        drop_in = True
    else:
        need_len = dur
        drop_in = False
    if not ctx.windows:
        return c["no_window_score"], None, True
    buf = walk if walk is not None else c["distance"]["default_walk_min"]
    best, best_w = 0.0, None
    for w in ctx.windows:
        if start.weekday() != w.weekday and not drop_in:
            continue
        # check each day the event covers (drop-ins can span days)
        day = start.date()
        while datetime.combine(day, time(0), tzinfo=start.tzinfo) < end:
            if day.weekday() == w.weekday:
                ws = datetime.combine(day, w.start, tzinfo=start.tzinfo)
                we = datetime.combine(day, w.end, tzinfo=start.tzinfo)
                if drop_in:
                    s = max(start, ws)
                    e = min(end, s + timedelta(minutes=need_len))
                    if s < we and e > s:
                        fit = min(1.0, max(0.0, _minutes(s, min(e, we))) / need_len) * 0.9
                    else:
                        fit = 0.0
                else:
                    need_s, need_e = start - timedelta(minutes=buf), end
                    overlap = _minutes(max(need_s, ws), min(need_e, we))
                    fit = max(0.0, overlap) / _minutes(need_s, need_e)
                if fit > best:
                    best, best_w = fit, w
            day += timedelta(days=1)
            if not drop_in:
                break
    if best_w is None:
        return 0.0, None, False
    label = f"Fits {window_phrase(best_w)}" if best >= 0.9 else f"Mostly inside {window_phrase(best_w)}"
    return round(best, 3), label, best >= c["min_window_fit"]


# --------------------------------------------------------------------------- components
def dimension_score(ctx: StudentCtx, item: KbItem) -> tuple[float, str]:
    if not ctx.focus:
        return 0.0, ""
    if ctx.focus in item.dims:
        return round(min(1.0, item.dims[ctx.focus]), 3), ctx.focus.capitalize()
    bcfg = barriers_config()["barriers"]
    for b in ctx.barriers:
        bc = bcfg.get(b, {})
        if ctx.focus in bc.get("root_cause_for", []) and item.causes & set(bc.get("causes", [])):
            return cfg()["root_cause_score"], f"root_cause:{next(iter(item.causes & set(bc['causes'])))}"
    return 0.0, ""


def _prefer_ok(pref: str, item: KbItem, walk: int | None, window_score: float) -> bool:
    dur = _minutes(item.starts_at, item.ends_at) if item.starts_at and item.ends_at else None
    return {
        "short": dur is None or dur <= 60,
        "near": walk is not None and walk <= 10,
        "online": item.campus == "online",
        "free": item.cost == "free",
        "solo_friendly": bool(item.solo_friendly),
        "structured": (item.rung == 2) or ("structured" in item.formats) or ("games" in item.formats),
        "low_rung": (item.rung or 1) <= 1,
        "in_window": window_score >= 0.9,
    }.get(pref, False)


def barrier_score(ctx: StudentCtx, item: KbItem, walk: int | None, window_score: float) -> tuple[float, list[str]]:
    if not ctx.barriers:
        return 0.0, []
    bcfg = barriers_config()["barriers"]
    hit = []
    for b in ctx.barriers:
        bc = bcfg.get(b, {})
        if b in item.barriers or (item.causes & set(bc.get("causes", []))):
            hit.append(b)
            continue
        prefs = bc.get("prefer", [])
        if prefs and sum(_prefer_ok(p, item, walk, window_score) for p in prefs) >= max(1, math.ceil(len(prefs) / 2)):
            hit.append(b)
    return round(len(hit) / len(ctx.barriers), 3), hit


def rung_score(ctx: StudentCtx, item: KbItem) -> float:
    r = item.rung or 1
    t = ctx.target_rung
    if r == t:
        return 1.0
    if r == t - 1:
        return 0.5
    if r < t:
        return 0.25
    return 0.0


def helped_score(item: KbItem, stats: HelpedStats) -> tuple[float, int, float]:
    k = cfg()["helped_prior_strength"]
    helped, n = stats.by_key.get(item.series_key or "", stats.by_key.get(item.id, (0, 0)))
    post = (helped + stats.prior * k) / (n + k)
    return round(post, 3), n, (helped / n if n else 0.0)


def memory_adjust(item: KbItem, memory: list[MemoryFact]) -> list[tuple[MemoryFact, float]]:
    mc = cfg()["memory"]
    out: list[tuple[MemoryFact, float]] = []
    for f in memory:
        d = 0.0
        if f.kind == "likes_format" and f.key in item.formats:
            d = mc["per_fact_max"] * min(1.0, f.confidence / 0.8)
        elif f.kind == "disliked_format" and f.key in item.formats:
            d = -mc["per_fact_max"]
        elif f.kind == "helped" and f.key in (item.series_key, *item.formats, *item.causes):
            d = mc["per_fact_max"]
        elif f.kind == "time_works" and item.starts_at is not None:
            day, _, part = f.key.partition("_")
            hr = item.starts_at.hour
            bucket = "morning" if hr < 12 else ("midday" if hr < 15 else ("afternoon" if hr < 17 else "evening"))
            if DAYS.get(day) == item.starts_at.weekday() and part == bucket:
                d = round(mc["per_fact_max"] * 0.6, 3)
        elif f.kind == "constraint" and f.key == "works_evenings" and item.starts_at is not None and item.starts_at.hour >= 17:
            d = -mc["per_fact_max"]
        if d:
            out.append((f, round(d, 3)))
    total = sum(d for _, d in out)
    cap = mc["total_cap"]
    if abs(total) > cap:
        scale = cap / abs(total)
        out = [(f, round(d * scale, 3)) for f, d in out]
    return out


# --------------------------------------------------------------------------- main
def score_item(ctx: StudentCtx, item: KbItem, stats: HelpedStats, memory: list[MemoryFact], now: datetime) -> Scored | None:
    c = cfg()
    filters: list[tuple[str, str]] = []
    # hard filters
    if item.kind == "micro":
        return None
    if item.campus not in (ctx.campus, "online"):
        return None
    if item.audiences and ctx.campus not in item.audiences:
        return None  # e.g. an online service only for Camden students
    filters.append(("online", "Online") if item.campus == "online" else ("campus", "On your campus"))
    if item.id in ctx.declined or item.id in ctx.committed:
        return None
    if item.starts_at is not None:
        end = item.ends_at or item.starts_at + timedelta(hours=1)
        if (item.all_day and end <= now) or (not item.all_day and item.starts_at <= now):
            return None
        if item.starts_at > now + timedelta(days=c["horizon_days"]):
            return None
    if ctx.free_only and item.cost == "paid":
        return None
    if item.cost == "free":
        filters.append(("free", "Free"))
    elif item.cost == "unknown":
        filters.append(("cost_unknown", "Cost not listed"))
    walk = walk_minutes(ctx, item)
    wscore, wlabel, wpass = window_fit(ctx, item, now, walk)
    if not wpass:
        return None
    if wlabel and wscore >= c["min_window_fit"] and ctx.windows and item.starts_at is not None:
        filters.append(("in_window", "Inside one of your free windows"))
    if item.starts_at is None and item.kind not in ("online",) and item.campus != "online" and not item.open_hours:
        filters.append(("hours_unknown", "Hours not listed here: check before you go"))
    if item.synthetic:
        filters.append(("sample", "Sample event (synthetic)"))

    dscore, dnote = dimension_score(ctx, item)
    bscore, bhits = barrier_score(ctx, item, walk, wscore)
    rscore = rung_score(ctx, item)
    hscore, hn, hraw = helped_score(item, stats)
    comps = {"dimension": dscore, "barrier": bscore, "window": wscore, "rung": rscore, "helped_similar": hscore}
    w = c["weights"]
    base = sum(w[k] * v for k, v in comps.items())
    mem = memory_adjust(item, memory)
    d = c["distance"]
    penalty = 0.0
    if walk is not None and walk > d["free_minutes"]:
        penalty = round(d["penalty_per_5_min"] * (walk - d["free_minutes"]) / 5, 3)
    total = round(base + sum(x for _, x in mem) - penalty, 4)
    texts = {
        "dimension": dnote,
        "barrier": ", ".join(bhits),
        "window": wlabel or "",
        "rung": c["rung_labels"].get(item.rung or 1, ""),
        "helped_similar": f"{round(hraw * 100)}% of {hn} {stats.cohort_label} rated it 4+" if hn else "No ratings yet",
    }
    distance_note = f"{walk}-minute walk" if walk is not None else ("Online" if item.campus == "online" else None)
    return Scored(item=item, score=total, components=comps, component_text=texts, filters=filters, memory=mem,
                  walk_min=walk, window_label=wlabel, distance_note=distance_note, penalty=penalty, helped_n=hn)


def _attrs(s: Scored) -> tuple:
    it = s.item
    return (it.kind, it.venue or it.id, it.starts_at.weekday() if it.starts_at else -1, it.rung or 1, it.series_key or it.id)


def diverse_top(scored: list[Scored], n: int = 3) -> list[Scored]:
    if not scored:
        return []
    need = cfg()["diversity_min_diff"]
    chosen = [scored[0]]
    for relax in (need, 1, 0):
        for s in scored[1:]:
            if len(chosen) >= n:
                break
            if s in chosen:
                continue
            a = _attrs(s)
            if any(a[4] == _attrs(x)[4] for x in chosen) and relax > 0:
                continue  # never two of the same series unless desperate
            if all(sum(p != q for p, q in zip(a, _attrs(x))) >= relax for x in chosen):
                chosen.append(s)
        if len(chosen) >= n:
            break
    return chosen[:n]


def _fallbacks(ctx: StudentCtx, items: list[KbItem], now: datetime) -> list[Scored]:
    """Never an empty card: open place, online option, then a 10-minute micro-step."""
    out = []
    focus = ctx.focus or "emotional"
    micro = [i for i in items if i.kind == "micro" and focus in i.dims and i.id not in ctx.declined]
    micro = micro or [i for i in items if i.kind == "micro" and i.id not in ctx.declined]
    for m in sorted(micro, key=lambda i: i.id)[:2]:
        out.append(Scored(item=m, score=0.0, components={k: 0.0 for k in cfg()["weights"]}, component_text={},
                          filters=[("micro", "A 10-minute step you can do anywhere")], memory=[], walk_min=None,
                          window_label="Any time", distance_note=None, fallback=True))
    return out


def rank(ctx: StudentCtx, items: list[KbItem], stats: HelpedStats, memory: list[MemoryFact], now: datetime,
         n: int = 3, explore: bool | None = None) -> RankResult:
    scored = [s for s in (score_item(ctx, it, stats, memory, now) for it in items) if s is not None]
    explore = cfg()["explore"] if explore is None else explore
    if explore:
        seed = int(hashlib.sha256(f"{ctx.id}:{now.isocalendar()[1]}".encode()).hexdigest()[:8], 16)
        rnd = random.Random(seed)
        k = cfg()["helped_prior_strength"]
        for s in scored:  # Thompson sample replaces the posterior mean
            h, cnt = stats.by_key.get(s.item.series_key or "", (0, 0))
            a, b = h + stats.prior * k, (cnt - h) + (1 - stats.prior) * k
            draw = rnd.betavariate(a, b)
            s.score = round(s.score + cfg()["weights"]["helped_similar"] * (draw - s.components["helped_similar"]), 4)
    scored.sort(key=lambda s: (-s.score, s.walk_min if s.walk_min is not None else 999, s.item.id))
    # don't lead with something irrelevant to the chosen area if anything relevant exists
    if ctx.focus:
        relevant = [s for s in scored if s.components["dimension"] > 0]
        scored = relevant + [s for s in scored if s.components["dimension"] == 0] if relevant else scored
    picks = diverse_top(scored, n)
    if len(picks) < n:
        picks += _fallbacks(ctx, items, now)[: n - len(picks)]
    return RankResult(care_first=ctx.care_first, picks=picks, considered=len(items), engine_version=cfg()["version"])
