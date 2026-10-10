"""Compass dummy dataset generator (SYNTHETIC - for the hackathon demo only).

Makes a realistic-looking fall 2026 semester of Wellness Inventory results for
1,500 made-up Rutgers students, plus Compass usage logs, sample events for
Newark and Camden, group challenges and anonymous wins.

Nothing here is real student data. Patterns (midterm and finals dips, group
differences, the effect of taking steps) are BUILT IN on purpose so the demo
has something to show. Replace with ScarletWell's de-identified export later.

Run:  python3 generate.py  [--seed 42]   (needs numpy + pandas)
"""
import argparse, json, math, re, html
from datetime import date, datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--students", type=int, default=1500)
ap.add_argument("--kb", default=str(Path(__file__).resolve().parent / "items.json"))
args = ap.parse_args()
rng = np.random.default_rng(args.seed)
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

DIMS = ["emotional", "environmental", "financial", "intellectual",
        "occupational", "physical", "social", "spiritual"]
SCALE_MIN, SCALE_MAX = 1.0, 4.0          # placeholder: mean of items on a 4-point scale
LOW, HIGH = 2.3, 3.2                     # placeholder band cut-offs; ask ScarletWell

# ---------------------------------------------------------------- calendar
# Real fall 2026 dates from scheduling.rutgers.edu/academic-calendar (checked 2026-10-10).
# The midterm window is NOT on the registrar calendar: it is an approximation.
CAL = {
    "source": "https://scheduling.rutgers.edu/academic-calendar/ (fall 2026 column, checked 2026-10-10)",
    "fall_begins": "2026-09-01",
    "thanksgiving_recess": ["2026-11-26", "2026-11-29"],
    "classes_end": "2026-12-10",
    "reading_days": ["2026-12-11", "2026-12-14"],
    "final_exams": ["2026-12-15", "2026-12-22"],
    "spring_begins": "2027-01-19",
    "midterm_window_APPROXIMATE": ["2026-10-05", "2026-10-30"],
    "note": "Midterms are not on the registrar calendar; the window above is an assumption for the demo.",
}
TERM_START, TERM_END = date(2026, 9, 1), date(2026, 12, 22)

def gauss(d, center, sd):
    return math.exp(-((d - center).days ** 2) / (2 * sd ** 2))

MID_C, FIN_C = date(2026, 10, 19), date(2026, 12, 16)

def time_effect(d, dim, s):
    e = 0.0
    m, f = gauss(d, MID_C, 8), gauss(d, FIN_C, 6)
    e += {"physical": -0.22, "emotional": -0.18, "intellectual": -0.12}.get(dim, 0) * m
    e += {"physical": -0.35, "emotional": -0.30, "intellectual": -0.20, "social": -0.10}.get(dim, 0) * f
    if dim == "social" and s["class_year"] == "first_year":
        e += -0.22 * math.exp(-(d - TERM_START).days / 21)          # early-term loneliness
    if dim == "financial" and s["first_gen"]:
        e += -0.15 * math.exp(-(d - TERM_START).days / 14)          # start-of-term costs
    if dim in ("social", "spiritual") and date(2026, 11, 23) <= d <= date(2026, 11, 29):
        e += 0.05
    return e

# ---------------------------------------------------------------- students
SCHOOLS = {
    "new_brunswick": ["School of Arts and Sciences", "School of Engineering", "Rutgers Business School-NB",
                      "School of Environmental and Biological Sciences", "Mason Gross School of the Arts",
                      "School of Nursing", "School of Communication and Information"],
    "newark": ["School of Arts and Sciences-Newark", "Rutgers Business School-Newark",
               "School of Public Affairs and Administration", "School of Criminal Justice"],
    "camden": ["Camden College of Arts and Sciences", "Rutgers School of Business-Camden",
               "School of Nursing-Camden"],
}
HOMES = {"new_brunswick": ["Busch", "College Avenue", "Livingston", "Cook/Douglass"],
         "newark": ["University Heights"], "camden": ["Camden waterfront"]}
BASE = {"emotional": 2.65, "environmental": 2.95, "financial": 2.55, "intellectual": 2.95,
        "occupational": 2.8, "physical": 2.65, "social": 2.75, "spiritual": 2.85}

students = []
for i in range(args.students):
    campus = rng.choice(["new_brunswick", "newark", "camden"], p=[0.70, 0.18, 0.12])
    level = "grad" if rng.random() < 0.18 else "undergrad"
    year = "grad" if level == "grad" else rng.choice(["first_year", "sophomore", "junior", "senior"], p=[.27, .25, .24, .24])
    p_res = {"new_brunswick": 0.55, "newark": 0.18, "camden": 0.15}[campus] * (0.15 if level == "grad" else 1)
    housing = "resident" if rng.random() < p_res else "commuter"
    first_gen = bool(rng.random() < {"new_brunswick": 0.30, "newark": 0.40, "camden": 0.40}[campus])
    works20 = bool(rng.random() < (0.35 if housing == "commuter" else 0.12))
    students.append(dict(
        student_id=f"S{i+1:05d}", campus=campus, level=level, class_year=year, housing=housing,
        first_gen=first_gen, works_20plus_hours=works20,
        school=rng.choice(SCHOOLS[campus]),
        home_area=rng.choice(HOMES[campus]) if housing == "resident" else "commutes",
        preferred_language="es" if rng.random() < (0.10 if campus != "new_brunswick" else 0.05) else "en",
        synthetic=True))
S = pd.DataFrame(students)

def baseline(s):
    g = rng.normal(0, 0.33)                     # general wellbeing
    b = {}
    for d in DIMS:
        v = BASE[d] + g + rng.normal(0, 0.30)
        if d == "social":
            v += -0.25 * (s["housing"] == "commuter") - 0.10 * s["first_gen"] - 0.05 * (s["level"] == "grad")
        if d == "financial":
            v += -0.30 * s["first_gen"] - 0.10 * s["works_20plus_hours"] - {"newark": 0.10, "camden": 0.15}.get(s["campus"], 0)
        if d == "physical":
            v += -0.15 * s["works_20plus_hours"]
        if d == "environmental":
            v += -0.05 * (s["housing"] == "commuter")
        if d == "occupational":
            v += 0.10 * (s["level"] == "grad")
        b[d] = v
    return b

# ---------------------------------------------------------------- knowledge base items
kb = json.load(open(args.kb))["items"]
def social_level(text):
    t = text.lower()
    if re.search(r"\b(mixer|social|party|meet ?up|club meeting|fair|night out|festival)\b", t): return 3
    if re.search(r"\b(game|cook|volunteer|class|craft|workshop|run|5k|walk|hike|garden|paint|dance|team)\b", t): return 2
    return 1
items = []
for it in kb:
    if it["type"] not in ("event", "resource", "study"): continue
    campus = {"New Brunswick": "new_brunswick", "Newark": "newark", "Camden": "camden"}.get(it["campus"], "online")
    title = html.unescape(it["title"])
    lvl = social_level(title + " " + it.get("summary", ""))
    items.append(dict(item_id=it["id"], kind=it["type"], title=title, campus=campus,
                      venue=it.get("venue") or it.get("program", ""), address=it.get("address", ""),
                      start=it.get("start", ""), end=it.get("end", ""),
                      dimensions="|".join(it.get("dimensions", [])), causes="|".join(it.get("causes", [])),
                      cost="free" if "free" in (it.get("cost") or "").lower() else "unknown",
                      social_level=lvl, solo_friendly=lvl <= 2,
                      source="wellness_calendar" if it["type"] == "event" else "scarletwell_list_or_verified",
                      synthetic=False))

VENUES = {
    "newark": [("Paul Robeson Campus Center", 40.7415, -74.1752), ("Golden Dome Athletic Center", 40.7428, -74.1787),
               ("John Cotton Dana Library", 40.7420, -74.1768), ("Bradley Hall", 40.7409, -74.1739)],
    "camden": [("Campus Center", 39.9486, -75.1222), ("Paul Robeson Library", 39.9481, -75.1232),
               ("Athletic and Fitness Center", 39.9497, -75.1198)],
}
TEMPLATES = [  # title, dimensions, social level, minutes
    ("Commuter lunch and board games", "social|financial", 2, 60), ("Chair yoga between classes", "physical|emotional", 1, 30),
    ("Study hall with free coffee", "intellectual|social", 1, 90), ("Budgeting for real life (workshop)", "financial", 1, 60),
    ("Open gym pickup basketball", "physical|social", 2, 60), ("Cook a cheap healthy dinner", "physical|financial|social", 2, 75),
    ("Resume drop-in", "occupational", 1, 45), ("Volunteer: campus garden", "environmental|social|spiritual", 2, 90),
    ("Mindful minutes", "emotional|spiritual", 1, 20), ("Club fair mixer", "social", 3, 90),
    ("Paint and decompress", "emotional|social", 2, 60), ("Interfaith dialogue lunch", "spiritual|social", 2, 60),
]
syn_id = 0
for campus, n in (("newark", 34), ("camden", 22)):
    for _ in range(n):
        t = TEMPLATES[rng.integers(len(TEMPLATES))]
        if campus == "camden" and "financial" in t[1] and rng.random() < 0.8:   # built-in supply gap
            t = TEMPLATES[1]
        v = VENUES[campus][rng.integers(len(VENUES[campus]))]
        day = date(2026, 10, 12) + timedelta(days=int(rng.integers(0, 64)))
        if day.weekday() >= 5: day += timedelta(days=7 - day.weekday())
        hour = int(rng.choice([11, 12, 13, 16, 17, 18]))
        st = datetime(day.year, day.month, day.day, hour, 0 if rng.random() < .6 else 30)
        syn_id += 1
        items.append(dict(item_id=f"syn-{campus}-{syn_id:03d}", kind="event", title=f"{t[0]} (sample)", campus=campus,
                          venue=v[0], address="", start=st.strftime("%Y-%m-%d %H:%M:%S"),
                          end=(st + timedelta(minutes=t[3])).strftime("%Y-%m-%d %H:%M:%S"),
                          dimensions=t[1], causes="", cost="free", social_level=t[2], solo_friendly=t[2] <= 2,
                          source="synthetic", synthetic=True, lat=v[1], lon=v[2]))
I = pd.DataFrame(items)
I["dimensions"] = I["dimensions"].fillna("")
I["start_d"] = pd.to_datetime(I["start"], errors="coerce").dt.date

# ---------------------------------------------------------------- inventory takes + Compass usage
results, log = [], []
for _, s in S.iterrows():
    b = baseline(s)
    joined = rng.random() < 0.60
    boost = {d: 0.0 for d in DIMS}
    t = TERM_START + timedelta(days=int(rng.integers(1, 30)))
    takes = [t]
    p_retake = 0.55 + (0.15 if joined else 0)
    while True:
        t = t + timedelta(days=int(rng.integers(21, 43)))
        if t > TERM_END or rng.random() > p_retake: break
        takes.append(t); p_retake *= 0.8
    # usage: one suggestion a week from first take until term end
    if joined:
        week = takes[0] + timedelta(days=int(rng.integers(0, 4)))
        while week <= date(2026, 12, 18):
            cur = {d: b[d] + time_effect(week, d, s) + boost[d] for d in DIMS}
            focus = min(cur, key=cur.get) if rng.random() < 0.7 else rng.choice(DIMS)
            # only items that exist that week: places/services any time, events within the next 10 days
            ok_time = (I.kind != "event") | ((I.start_d >= week) & (I.start_d <= week + timedelta(days=10)))
            here = I.campus.isin([s.campus, "online"]) & ok_time
            pool = I[here & I.dimensions.str.contains(focus)]
            if pool.empty: pool = I[here]
            it = pool.iloc[int(rng.integers(len(pool)))]
            p_commit = 0.38 - 0.06 * (s.housing == "commuter") + 0.08 * (bool(it.solo_friendly) and cur["social"] < LOW)
            committed = rng.random() < p_commit
            invited = committed and rng.random() < 0.30
            friend = invited and rng.random() < 0.45
            attended = committed and rng.random() < (0.55 + 0.15 * friend)
            helped = int(np.clip(round(rng.normal(3.6, 0.9)), 1, 5)) if attended else None
            if attended:
                for d in str(it.dimensions).split("|"):
                    if d in boost: boost[d] = min(boost[d] + 0.07 * (helped - 2.5), 0.4)
            log.append(dict(student_id=s.student_id, suggested_on=week.isoformat(), item_id=it.item_id,
                            focus_dimension=focus, committed=committed, invited_friend=invited, friend_joined=friend,
                            attended=attended, helped_1to5=helped, synthetic=True))
            week += timedelta(days=7)
            if rng.random() < 0.06: break                      # some students drift away
    for k, d0 in enumerate(takes):
        # usage boost only counts for takes after the steps happened (approximation: scale by progress)
        frac = min(1.0, max(0.0, (d0 - takes[0]).days / 90))
        row = dict(student_id=s.student_id, take_no=k + 1, taken_on=d0.isoformat(), source="synthetic")
        for d in DIMS:
            v = b[d] + time_effect(d0, d, s) + boost[d] * frac + rng.normal(0, 0.12)
            row[d] = round(float(np.clip(v, SCALE_MIN, SCALE_MAX)), 2)
        row["total"] = round(float(np.mean([row[d] for d in DIMS])), 2)
        results.append(row)
R = pd.DataFrame(results)
L = pd.DataFrame(log)

# ---------------------------------------------------------------- demo personas (hand-made, also synthetic)
personas = json.load(open(Path(__file__).resolve().parent / "personas.json"))
for p in personas:
    S.loc[len(S)] = dict(student_id=p["student_id"], campus=p["campus"], level=p["level"], class_year=p["class_year"],
                         housing=p["housing"], first_gen=p["first_gen"], works_20plus_hours=p["works_20plus_hours"],
                         school=p["school"], home_area=p["home_area"], preferred_language=p["preferred_language"], synthetic=True)
    for k, tk in enumerate(p["takes"]):
        row = dict(student_id=p["student_id"], take_no=k + 1, taken_on=tk["taken_on"], source="synthetic_persona")
        row.update({d: tk[d] for d in DIMS}); row["total"] = round(float(np.mean([tk[d] for d in DIMS])), 2)
        R.loc[len(R)] = row

# ---------------------------------------------------------------- challenges + wins (synthetic)
steps = L[L.attended].merge(S[["student_id", "campus"]], on="student_id")
steps["week"] = pd.to_datetime(steps.suggested_on).dt.to_period("W-SUN").dt.start_time.dt.date.astype(str)
wk = steps[steps.week == "2026-10-05"].groupby("campus").size().to_dict()
challenges = [
    {"challenge_id": "ch-campus-cup-oct", "title": "Scarlet Wellness Cup: steps this week", "scope": "campus",
     "week_of": "2026-10-05", "goal_per_campus": {"new_brunswick": 400, "newark": 110, "camden": 70},
     "progress": {c: int(wk.get(c, 0)) for c in ("new_brunswick", "newark", "camden")},
     "rule": "Cooperative: each campus races its own goal, sized to enrollment. No individual leaderboard.", "synthetic": True},
    {"challenge_id": "ch-sleep-week", "title": "Sleep Week: three wind-down nights", "scope": "all",
     "week_of": "2026-10-19", "dimension": "physical", "rule": "Timed for midterms. Counts check-ins, not hours slept.", "synthetic": True},
    {"challenge_id": "ch-busch-halls", "title": "Busch residence halls: bring-a-friend week", "scope": "hall",
     "week_of": "2026-11-02", "dimension": "social", "rule": "Steps taken with a friend count double.", "synthetic": True},
]
wins = json.load(open(Path(__file__).resolve().parent / "wins.json"))

# ---------------------------------------------------------------- write
S.to_csv(OUT / "students.csv", index=False)
R.sort_values(["student_id", "take_no"]).to_csv(OUT / "inventory_results.csv", index=False)
L.to_csv(OUT / "compass_usage_log.csv", index=False)
I.drop(columns=["start_d"]).to_csv(OUT / "kb_items_with_samples.csv", index=False)
json.dump(CAL, open(OUT / "academic_calendar_fall2026.json", "w"), indent=2)
json.dump(challenges, open(OUT / "challenges.json", "w"), indent=2)
json.dump(wins, open(OUT / "wins.json", "w"), indent=2)
json.dump(personas, open(OUT / "personas.json", "w"), indent=2)
print(f"students {len(S)}  takes {len(R)}  usage rows {len(L)}  kb items {len(I)} ({int(I.synthetic.sum())} sample)")
