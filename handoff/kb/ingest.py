"""Starter knowledge-base builder for Compass.
Pulls upcoming events from the ScarletWell Wellness Calendar API, parses the
ScarletWell resource list, adds verified Newark/Camden resources, and writes items.json.
Dimension/cause tags here are keyword-based placeholders: replace with Claude Haiku tagging."""
import json, re, html, sys, urllib.request, datetime

API = "https://wellnesscalendar.rutgers.edu/wp-json/tribe/events/v1/events"
DIMS = ["emotional","environmental","financial","intellectual","occupational","physical","social","spiritual"]
KW = {
 "physical": ["5k","run","yoga","fitness","exercise","walk","rec","recreation","movement","dance","sport","health center","nutrition","farmers market","sleep","dining"],
 "emotional": ["mental","stress","mindful","meditat","counsel","calm","anxiety","wellbeing","well-being","self-care","resilien","caps","coping"],
 "social": ["social","meet","community","club","peer","connect","group","volunteer","festival","party","game"],
 "environmental": ["garden","nature","plant","outdoor","green","farm","park","environment","preserve","greenhouse","kokedama"],
 "intellectual": ["learning","learn","workshop","lecture","library","tutor","study","art","music","museum","read","talk"],
 "financial": ["financial","money","budget","food pantry","basic needs","snap","scarlet$ense","afford","free food"],
 "spiritual": ["spiritual","faith","meditation room","interfaith","purpose","reflection","prayer"],
 "occupational": ["career","job","internship","resume","handshake","professional","occupational"],
}
CAUSE_KW = {
 "academic_workload": ["tutor","learning center","study","academic"],
 "stress": ["stress","calm","mindful","meditat","yoga","counsel","relax"],
 "loneliness": ["social","meet","community","peer","club","group","volunteer"],
 "money": ["financial","food pantry","basic needs","snap","budget","free food","farmers market"],
 "sleep_habits": ["sleep"],
 "inactivity": ["5k","run","fitness","exercise","walk","rec","dance","yoga","movement"],
 "purpose": ["career","purpose","faith","spiritual","volunteer"],
}
def _hit(t, w):
    return re.search(r"(?<![a-z])" + re.escape(w.strip()) + r"(?![a-z])", t) is not None
def tag(text, base=None):
    t = text.lower()
    dims = sorted({d for d,ws in KW.items() if any(_hit(t, w) for w in ws)} | set(base or []))
    causes = sorted({c for c,ws in CAUSE_KW.items() if any(_hit(t, w) for w in ws)})
    return dims, causes

def clean(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()

def pull_events(start):
    out, page = [], 1
    while True:
        url = f"{API}?per_page=50&page={page}&start_date={start}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Compass hackathon prototype)", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        out += d.get("events", [])
        if page >= d.get("total_pages", 1): break
        page += 1
    return out

CAT2DIM = {"Art/Music":["intellectual","social"],"Emotional/Mental Health":["emotional"],"Environment/Nature":["environmental"],"Physical/Movement":["physical"],"Wellness Week":[],"Other":[]}

def events_to_items(evs, today):
    items = []
    for e in evs:
        v = e.get("venue") if isinstance(e.get("venue"), dict) else {}
        cats = [c["name"] for c in e.get("categories", [])]
        base = sorted({d for c in cats for d in CAT2DIM.get(c, [])})
        title = clean(e["title"]); desc = clean(e.get("description"))[:600]
        dims, causes = tag(title + " " + desc, base)
        cost = clean(e.get("cost")) or "free (no cost listed)"
        city = (v.get("city") or "")
        campus = "New Brunswick" if city in ("New Brunswick","Piscataway","") else city
        if e.get("is_virtual"): campus = "Online"
        items.append({
          "id": f"evt-{e['id']}-{e['start_date'][:10]}", "type": "event", "title": title,
          "campus": campus, "venue": clean(v.get("venue")), "address": ", ".join(x for x in [v.get("address"), city] if x) or None,
          "start": e.get("start_date"), "end": e.get("end_date"), "all_day": e.get("all_day"),
          "cost": cost, "calendar_categories": cats, "dimensions": dims, "causes": causes,
          "summary": desc[:280], "url": e.get("url"),
          "source": "ScarletWell Wellness Calendar API", "last_checked": today,
          "tags_method": "keyword placeholder: replace with Claude Haiku tagging"})
    return items

DIM_HEAD = {"Physical Wellness":"physical","Intellectual Wellness":"intellectual","Emotional Wellness":"emotional","Financial Wellness":"financial","Social Wellness":"social","Spiritual Wellness":"spiritual","Occupational Wellness":"occupational","Environmental Wellness":"environmental"}
def parse_scarletwell(path, today):
    """Turn the ScarletWell resource list into location records (one per address line)."""
    lines = [l.strip() for l in open(path).read().splitlines()]
    items, dim, program = [], None, None
    for i, l in enumerate(lines):
        if not l: continue
        if l in DIM_HEAD: dim = DIM_HEAD[l]; continue
        if l.startswith("-   ") or l.startswith("- "):
            program = clean(l.lstrip("- ").split("—")[0].strip(" (")); continue
        m = re.match(r"^\(?([^:]{3,120}):\s*(.+)$", l)
        if dim and m and re.search(r"\d", m.group(2)) and "NJ" in l:
            name = clean(m.group(1)); addr = clean(m.group(2)).rstrip(")")
            phone = None
            for nxt in lines[i+1:i+4]:
                p = re.search(r"\(?\d{3}\)?[\s-]?\d{3}[\s-]?\w{4}", nxt)
                if p: phone = p.group(0); break
            dims, causes = tag(f"{program or ''} {name}", [dim])
            if program and "Learning Center" in program + name: causes = sorted(set(causes)|{"academic_workload"})
            items.append({"id": f"res-nb-{len(items)+1:03d}", "type": "resource", "title": name,
              "program": program, "campus": "New Brunswick", "address": addr, "phone": phone,
              "dimensions": dims, "causes": causes, "cost": "free for students (verify)",
              "source": "ScarletWell resource list (challenge file)", "last_checked": today})
    return items

def verified_extra(today):
    base = {"last_checked": today, "cost": "free for students"}
    rows = [
     {"id":"res-nwk-001","type":"resource","title":"Rutgers–Newark Counseling Center","campus":"Newark","address":"Blumenthal Hall, 249 University Ave, Room 101, Newark, NJ 07102","phone":"(973) 353-5805","dimensions":["emotional"],"causes":["stress","loneliness"],"access":"appointment or telehealth; group therapy; workshops","url":"https://studentaffairs.newark.rutgers.edu/health-wellness/counseling-center","source":"Rutgers–Newark Student Affairs"},
     {"id":"res-nwk-002","type":"resource","title":"pantry+ at RU-N (food pantry)","campus":"Newark","dimensions":["financial","physical"],"causes":["money"],"access":"online ordering available","url":"https://studentaffairs.newark.rutgers.edu/health-wellness","source":"Rutgers–Newark Student Affairs (address to confirm)"},
     {"id":"res-cmd-001","type":"resource","title":"Rutgers–Camden Student Wellness Center","campus":"Camden","address":"326 Penn Street, Campus Center 2nd floor, Camden, NJ","phone":"856-225-6005","hours":"Mon–Fri 8:30 am–4:30 pm; some evening hours (confirm)","dimensions":["emotional","physical"],"causes":["stress","sleep_habits"],"url":"https://wellnesscenter.camden.rutgers.edu/","source":"Rutgers–Camden Student Wellness Center"},
     {"id":"res-cmd-002","type":"resource","title":"Uwill free teletherapy (Camden students)","campus":"Online","dimensions":["emotional"],"causes":["stress"],"access":"online, evenings and weekends","url":"https://app.uwill.com","source":"Rutgers–Camden Student Wellness Center"},
     {"id":"res-cmd-003","type":"resource","title":"Togetherall 24/7 peer support community","campus":"Online","dimensions":["emotional","social"],"causes":["loneliness","stress"],"access":"online, 24/7, moderated by licensed practitioners","url":"https://togetherall.com","source":"Rutgers–Camden Student Wellness Center"},
     {"id":"res-cmd-004","type":"resource","title":"Rutgers–Camden Food Pantry","campus":"Camden","dimensions":["financial","physical"],"causes":["money"],"source":"Rutgers–Camden Student Wellness Center (address to confirm)"},
     {"id":"study-001","type":"study","title":"Rutgers Sleep Lab: current research studies","campus":"New Brunswick","phone":"(848) 932-7037","email":"sleep-lab@kines.rutgers.edu","dimensions":["physical"],"causes":["sleep_habits"],"access":"opt-in research; check eligibility (some studies are for teens 14–17)","url":"https://kines.rutgers.edu/sleep-lab-participate-in-a-study","source":"Rutgers Kinesiology Sleep Lab"},
    ]
    return [{**base, **r} for r in rows]

CRISIS = [
 {"name":"988 Suicide & Crisis Lifeline","contact":"call or text 988","campus":"all"},
 {"name":"Crisis Text Line","contact":"text TALK to 741741","campus":"all"},
 {"name":"CAPS (New Brunswick)","contact":"848-932-7884","campus":"New Brunswick"},
 {"name":"Rutgers–Newark Counseling Center","contact":"(973) 353-5805","campus":"Newark"},
 {"name":"Rutgers–Camden Student Wellness Center","contact":"856-225-6005","campus":"Camden"},
 {"name":"Camden County Crisis Screening","contact":"1-856-428-4357","campus":"Camden"},
 {"name":"Emergency","contact":"911","campus":"all"},
]

if __name__ == "__main__":
    today = datetime.date.today().isoformat()
    evs = pull_events(today)
    items = events_to_items(evs, today) + parse_scarletwell("scarletwell.txt", today) + verified_extra(today)
    json.dump({"generated": today, "count": len(items), "items": items, "crisis_lines_verify_before_demo": CRISIS},
              open("items.json","w"), indent=2, ensure_ascii=False)
    from collections import Counter
    print("items:", len(items), Counter(i["type"] for i in items), Counter(i["campus"] for i in items))
    print("dimension coverage:", Counter(d for i in items for d in i["dimensions"]))
