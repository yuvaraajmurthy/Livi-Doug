"""Build v0 fixtures from the contract models (so every fixture validates by construction).

Later, scripts/record_fixtures.py overwrites these with responses recorded from the live API.
Run: python -m scripts.build_fixtures
"""
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.models.common import CrisisLine, CrisisResponse, GoingCount, Item, Place, SourceRef, SupportCard, SupportOption
from app.models.demo import PersonasResponse, ResetResponse, SessionResponse, SkipAheadResponse
from app.models.loop import (
    ArcStatus, ChallengeProgress, CommitResponse, FiredNotification, FollowupResponse, InviteAccepted,
    InviteView, NextRung, ProgressDelta, SubscriptionResult,
)
from app.models.social import Challenge, PulseResponse, SameHere, Win, WinAccepted
from app.models.staff import (
    CalendarOverlay, Dip, DipsResponse, FunnelResponse, FunnelRow, GapRow, GapsResponse, RetakeRow,
    RetakesResponse, StaffFilters, WeeklyPoint, WeeklyResponse,
)
from app.models.student import (
    CardResponse, Component, DeleteResult, DimensionScore, InboxItem, InboxResponse, MapResponse,
    MemoryItem, MemoryList, MemoryReason, MemorySource, NextResponse, Profile, ProfileResult, ReasonLine,
    Reasons, RetakeNudge, StudentSummary, Suggestion, Take,
)
from app.services.demo import PERSONAS

NY = ZoneInfo("America/New_York")
NOW = datetime(2026, 10, 12, 9, 0, tzinfo=NY)
OUT = Path(__file__).resolve().parent.parent / "fixtures"
W = {"dimension": 0.35, "barrier": 0.25, "window": 0.20, "rung": 0.10, "helped_similar": 0.10}
LABEL = {"emotional": "Emotional", "environmental": "Environmental", "financial": "Financial", "intellectual": "Intellectual",
         "occupational": "Occupational", "physical": "Physical", "social": "Social", "spiritual": "Spiritual"}
RUNG = {1: "Just show up", 2: "Structured: you'll be doing something, not mingling", 3: "Open social"}

CRISIS_LINES = [
    CrisisLine(id=1, name="988 Suicide & Crisis Lifeline", kind="call", contact="Call or text 988", href="tel:988", hours="24/7", campus="all", verified=False),
    CrisisLine(id=2, name="988 en español", kind="call", contact="Llama al 988 y marca 2, o envía AYUDA al 988", href="tel:988", hours="24/7", campus="all", language="es", verified=False),
    CrisisLine(id=3, name="Crisis Text Line", kind="text", contact="Text HOME to 741741", href="sms:741741?body=HOME", hours="24/7", campus="all", verified=False),
    CrisisLine(id=4, name="Emergency", kind="emergency", contact="Call 911", href="tel:911", hours="24/7", campus="all", verified=False),
]
CAMPUS_LINES = {
    "new_brunswick": CrisisLine(id=5, name="CAPS (New Brunswick)", kind="call", contact="848-932-7884 (after hours, follow the prompts to reach a counselor)", href="tel:+18489327884", hours="24/7 via after-hours line", campus="new_brunswick", verified=False),
    "newark": CrisisLine(id=6, name="Rutgers–Newark Counseling Center", kind="call", contact="973-353-5805; after hours Uwill crisis line 833-646-1526", href="tel:+19733535805", hours="Mon–Fri 8:30–4:30; Uwill 24/7", campus="newark", verified=False),
    "camden": CrisisLine(id=7, name="Rutgers–Camden Student Wellness Center", kind="call", contact="856-225-6005; after hours Uwill crisis line 833-646-1526", href="tel:+18562256005", hours="Mon–Fri 8:30–4:30; Uwill 24/7", campus="camden", verified=False),
}


def lines(campus):
    return CRISIS_LINES + [CAMPUS_LINES[campus]]


def crisis(campus):
    return CrisisResponse(
        synthetic=True, now=NOW, title="You don't have to handle this alone",
        message="It sounds like things are really hard right now. You can reach a real person right now, any time, for free.",
        lines=lines(campus),
    )


def take(no, d, scores):
    total = round(sum(scores.values()) / 8, 2)
    return Take(take_no=no, taken_on=d, total=total, scores=scores)


def band(s):
    return "low" if s < 2.3 else ("high" if s >= 3.2 else "middle")


BLURB = {
    "high": "This is a real strength for you right now.",
    "middle": "Steady. Worth keeping an eye on.",
    "low": "An area with room to grow. Small steps count here.",
}


def dims(scores, prev=None):
    order = sorted(scores, key=lambda d: (-scores[d], d))
    return [DimensionScore(dimension=d, label=LABEL[d], score=scores[d], band=band(scores[d]), blurb=BLURB[band(scores[d])],
                           change=round(scores[d] - prev[d], 2) if prev else None) for d in order]


def reasons(dim_s, bar_s, win_s, rung_s, help_s, filters, memory=(), distance=None, texts=None):
    texts = texts or {}
    comps = []
    for name, s in (("dimension", dim_s), ("barrier", bar_s), ("window", win_s), ("rung", rung_s), ("helped_similar", help_s)):
        comps.append(Component(name=name, weight=W[name], score=s, contribution=round(W[name] * s, 3), text=texts.get(name, "")))
    total = round(sum(c.contribution for c in comps) + sum(m.delta for m in memory), 3)
    return Reasons(filters=[ReasonLine(code=c, text=t) for c, t in filters], components=comps, memory=list(memory), distance=distance, total=total)


def sugg(rec_id, item, start, end, when, window, place, walk, cost, cost_label, rung, going, rs, why, src, pushed=True):
    return Suggestion(rec_id=rec_id, item=item, starts_at=start, ends_at=end, when_label=when, window_label=window, where=place,
                      walk_min=walk, cost=cost, cost_label=cost_label, rung=rung, rung_label=RUNG.get(rung) if rung else None,
                      going=going, reasons=rs, why=why, why_source="template", pushed=pushed, source=src)


def dt(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=NY)


SAMPLE = SourceRef(name="Compass sample event (synthetic)")
F_CAMPUS = ("campus", "On your campus")
F_WINDOW = ("in_window", "Inside one of your free windows")
F_FREE = ("free", "Free")

# ---------------------------------------------------------------------------- personas
P = {}

andre_t1 = {"emotional": 2.6, "environmental": 2.9, "financial": 2.1, "intellectual": 3.2, "occupational": 3.0, "physical": 2.7, "social": 1.9, "spiritual": 3.4}
lunch = Item(id="pin-andre-lunch-2026-10-13", kind="event", title="Commuter lunch and board games (sample)",
             summary="Drop-in lunch with board and card games for commuter students. Food provided.", dimensions=["social", "financial"], synthetic=True)
robeson = Place(venue="Paul Robeson Campus Center", address="350 Dr. Martin Luther King Jr. Blvd, Newark, NJ 07102", lat=40.7415, lon=-74.1752, campus="newark")
andre_pick = sugg(
    101, lunch, dt(2026, 10, 13, 12, 30), dt(2026, 10, 13, 13, 30), "Tue Oct 13, 12:30–1:30 PM", "Fits your Tuesday gap, 12:20–2:30",
    robeson, 3, "free", "Free lunch", 2, GoingCount(count=14, label="14 Newark students are going"),
    reasons(1.0, 1.0, 1.0, 1.0, 0.72, [F_CAMPUS, F_WINDOW, F_FREE],
            distance="3-minute walk",
            texts={"dimension": "Social", "barrier": "Fits 'no time' and 'I don't know anyone'", "window": "Fits your Tuesday gap",
                   "rung": "Structured: you'll be playing, not mingling", "helped_similar": "Rated 4+ by 72% of 36 Newark commuters"}),
    "It's in your Tuesday gap, three minutes away, free, and the games give everyone something to do besides small talk.", SAMPLE)
gym = Item(id="syn-newark-012", kind="event", title="Open gym pickup basketball (sample)", summary="Casual pickup games, all levels.", dimensions=["physical", "social"], synthetic=True)
dana = Item(id="place-libcal-dana", kind="place", title="Study space at Dana Library", summary="Open study rooms you can book or drop into.",
            dimensions=["intellectual"], url="https://libcal.rutgers.edu/spaces?lid=2558", hours_text="Typical hours shown on LibCal", synthetic=False)
andre_alts = [
    sugg(102, Item(id="syn-newark-016", kind="event", title="Interfaith dialogue lunch (sample)", summary="Lunch and a guided conversation.", dimensions=["spiritual", "social"], synthetic=True),
         dt(2026, 10, 26, 12, 0), dt(2026, 10, 26, 13, 0), "Mon Oct 26, 12–1 PM", None, robeson, 3, "free", "Free lunch", 2,
         GoingCount(count=None, label="A few students are going"),
         reasons(1.0, 0.5, 0.5, 1.0, 0.6, [F_CAMPUS, F_FREE], distance="3-minute walk",
                 texts={"dimension": "Social", "barrier": "Fits 'I don't know anyone'", "window": "Not in your usual gap", "rung": "Structured", "helped_similar": "Rated 4+ by 60% of similar students"}),
         "Builds on your strongest area, spiritual, with a built-in topic so it's easy to join in.", SAMPLE),
    sugg(103, gym, dt(2026, 10, 20, 12, 0), dt(2026, 10, 20, 13, 0), "Tue Oct 20, 12–1 PM", "Fits your Tuesday gap, 12:20–2:30",
         Place(venue="John Cotton Dana Library", address=None, lat=40.742, lon=-74.1768, campus="newark"), 5, "free", "Free", 2,
         GoingCount(count=6, label="6 Newark students are going"),
         reasons(1.0, 0.5, 0.8, 1.0, 0.55, [F_CAMPUS, F_WINDOW, F_FREE], distance="5-minute walk",
                 texts={"dimension": "Social", "barrier": "Fits 'no time'", "window": "Mostly inside your Tuesday gap", "rung": "Structured", "helped_similar": "Rated 4+ by 55% of similar students"}),
         "A game to play means you meet people without having to start a conversation.", SAMPLE),
]

P["andre"] = dict(
    campus="newark", sid="DEMO-ANDRE", t1=andre_t1, focus="social", barriers=["no_time", "dont_know_anyone"],
    windows=["Tue 12:20-14:30", "Thu 12:20-14:30"], rung=2, lang="en", pick=andre_pick, alts=andre_alts,
    housing="commuter", level="undergrad",
)

priya_t1 = {"emotional": 2.5, "environmental": 3.1, "financial": 2.9, "intellectual": 2.3, "occupational": 3.0, "physical": 2.0, "social": 3.1, "spiritual": 2.7}
blc = Item(id="res-nb-023", kind="resource", title="Busch Learning Center", summary="Free tutoring and study groups, including math and science courses.",
           dimensions=["intellectual"], url="https://rlc.rutgers.edu/", phone=None, hours_text="Check current tutoring hours on the Learning Centers site")
blc_place = Place(venue="Rutgers Learning Centers", address="118 Frelinghuysen Road, Piscataway, NJ 08854", lat=40.5226, lon=-74.4627, campus="new_brunswick")
priya_pick = sugg(
    201, blc, None, None, "Drop in this week", None, blc_place, 4, "free", "Free for students", 1, GoingCount(count=None, label=""),
    reasons(0.7, 1.0, 0.5, 1.0, 0.68, [F_CAMPUS, F_FREE, ("hours_unknown", "Hours not listed here: check before you go")], distance="4-minute walk",
            texts={"dimension": "Addresses what's cutting into your sleep (coursework)", "barrier": "Fits 'coursework is eating my time'",
                   "window": "Open-hours place", "rung": "Just show up", "helped_similar": "Rated 4+ by 68% of 41 Busch residents"}),
    "Calc II is what's eating your nights, so getting help with the problem sets is the sleep step. Four minutes from you, free.",
    SourceRef(name="ScarletWell resource list", url="https://newbrunswick.rutgers.edu/scarletwell/wellness-resources", verified_on=date(2026, 10, 10)),
)
priya_alts = [
    sugg(202, Item(id="evt-10003706-2026-10-15", kind="event", title="Rutgers Big Chill 5K – Register Now!", dimensions=["physical", "social"]),
         dt(2026, 10, 15, 10), dt(2026, 10, 15, 11), "Thu Oct 15, 10–11 AM", None,
         Place(venue="College Ave Gym", address="130 College Ave, New Brunswick", lat=40.5017, lon=-74.4497, campus="new_brunswick"), None,
         "unknown", "Cost not listed", 2, GoingCount(count=None, label=""),
         reasons(1.0, 0.0, 0.5, 0.5, 0.5, [F_CAMPUS, ("cost_unknown", "Cost not listed")], distance="Bus ride from Busch",
                 texts={"dimension": "Physical", "barrier": "", "window": "", "rung": "", "helped_similar": ""}),
         "Moving earlier in the day can make it easier to wind down at night.",
         SourceRef(name="ScarletWell Wellness Calendar", url="https://wellnesscalendar.rutgers.edu/")),
    sugg(203, Item(id="micro-physical-1", kind="micro", title="10-minute wind-down: phone across the room at midnight", dimensions=["physical"]),
         None, None, "Tonight", None, Place(campus="online"), None, "free", "Free", 1, GoingCount(count=None, label=""),
         reasons(1.0, 0.0, 1.0, 1.0, 0.0, [F_FREE], texts={"dimension": "Physical", "barrier": "", "window": "Any time", "rung": "Just you", "helped_similar": ""}),
         "A tiny step for the nights the problem set runs late.", SourceRef(name="Compass micro-steps")),
]
P["priya"] = dict(campus="new_brunswick", sid="DEMO-PRIYA", t1=priya_t1, focus="physical", barriers=["coursework"], windows=[], rung=1, lang="en",
                  pick=priya_pick, alts=priya_alts, housing="resident", level="undergrad")

taylor_t1 = {"emotional": 1.3, "environmental": 2.5, "financial": 2.4, "intellectual": 2.2, "occupational": 2.4, "physical": 1.9, "social": 1.6, "spiritual": 2.3}
caps = SupportCard(
    title="Talking to someone can help",
    message="Your results suggest this might be a heavy stretch. That's not a label, just a reason to put a person first. All of these are free for Rutgers students.",
    options=[
        SupportOption(name="CAPS (Counseling, ADAP & Psychiatric Services)", kind="in_person", contact="848-932-7884", url="https://health.rutgers.edu/medical-and-counseling-services/counseling-services", address="17 Senior Street, New Brunswick, NJ 08901", hours="Call for same-week options; after hours follow the prompts", campus="new_brunswick"),
        SupportOption(name="Uwill teletherapy", kind="teletherapy", url="https://app.uwill.com", hours="Evenings and weekends available", campus="online"),
        SupportOption(name="Togetherall peer community", kind="peer", url="https://togetherall.com", hours="24/7, moderated", campus="online"),
    ],
)
taylor_pick = sugg(301, Item(id="evt-4457-2026-10-13", kind="event", title="LSM Pumpkin Decorating Event", dimensions=["emotional", "intellectual", "social"]),
                   dt(2026, 10, 13, 14), dt(2026, 10, 13, 16), "Tue Oct 13, 2–4 PM", None,
                   Place(venue="Library of Science and Medicine", address="165 Bevier Rd, Piscataway", lat=40.5236, lon=-74.4648, campus="new_brunswick"),
                   None, "unknown", "Cost not listed", 1, GoingCount(count=None, label=""),
                   reasons(1.0, 0.0, 0.5, 1.0, 0.5, [F_CAMPUS], texts={"dimension": "Emotional", "barrier": "", "window": "", "rung": "Just show up", "helped_similar": ""}),
                   "Low-key and hands-on, whenever you feel up for it.", SourceRef(name="ScarletWell Wellness Calendar", url="https://wellnesscalendar.rutgers.edu/"), pushed=False)
P["taylor"] = dict(campus="new_brunswick", sid="DEMO-TAYLOR", t1=taylor_t1, focus=None, barriers=[], windows=[], rung=1, lang="en",
                   pick=taylor_pick, alts=[], housing="resident", level="undergrad", care=caps)

sofia_t1 = {"emotional": 2.6, "environmental": 2.8, "financial": 1.9, "intellectual": 3.0, "occupational": 3.5, "physical": 2.6, "social": 2.5, "spiritual": 2.2}
pantry = Item(id="res-cmd-004", kind="resource", title="Rutgers–Camden Food Pantry", summary="Free food for Rutgers–Camden students.", dimensions=["financial", "physical"])
sofia_pick = sugg(401, pantry, None, None, "Esta semana", None, Place(venue="Rutgers–Camden", address=None, lat=39.9483, lon=-75.1224, campus="camden"), None,
                  "free", "Gratis para estudiantes", 1, GoingCount(count=None, label=""),
                  reasons(1.0, 1.0, 0.5, 1.0, 0.5, [F_CAMPUS, F_FREE, ("hours_unknown", "Horario no publicado aquí")],
                          texts={"dimension": "Financiero", "barrier": "Ayuda con 'el dinero no alcanza'", "window": "Lugar con horario", "rung": "Solo ve", "helped_similar": ""}),
                  "Comida gratis en tu campus, para que el dinero alcance un poco más esta semana.",
                  SourceRef(name="Rutgers–Camden Student Wellness Center", url="https://wellnesscenter.camden.rutgers.edu/"))
sofia_alts = [
    sugg(402, Item(id="syn-camden-043", kind="event", title="Cook a cheap healthy dinner (sample)", dimensions=["physical", "financial", "social"], synthetic=True),
         dt(2026, 10, 16, 17, 30), dt(2026, 10, 16, 18, 45), "Vie 16 oct, 5:30–6:45 PM", None,
         Place(venue="Athletic and Fitness Center", lat=39.9497, lon=-75.1208, campus="camden"), None, "free", "Gratis", 2,
         GoingCount(count=None, label="Van algunos estudiantes"),
         reasons(1.0, 0.5, 0.5, 0.5, 0.5, [F_CAMPUS, F_FREE], texts={"dimension": "Financiero", "barrier": "", "window": "", "rung": "", "helped_similar": ""}),
         "Una cena barata que puedes repetir en casa.", SAMPLE),
    sugg(403, Item(id="res-cmd-002", kind="online", title="Uwill free teletherapy (Camden students)", dimensions=["emotional"]),
         None, None, "Cuando quieras", None, Place(campus="online"), None, "free", "Gratis", 1, GoingCount(count=None, label=""),
         reasons(0.0, 0.5, 1.0, 1.0, 0.0, [("online", "En línea")], texts={"dimension": "", "barrier": "", "window": "", "rung": "", "helped_similar": ""}),
         "Por si el estrés del dinero pesa: en línea, de noche o fin de semana.", SourceRef(name="Rutgers–Camden Student Wellness Center", url="https://wellnesscenter.camden.rutgers.edu/")),
]
P["sofia"] = dict(campus="camden", sid="DEMO-SOFIA", t1=sofia_t1, focus="financial", barriers=["no_time", "money"], windows=[], rung=1, lang="es",
                  pick=sofia_pick, alts=sofia_alts, housing="commuter", level="grad")

jordan_t1 = {"emotional": 2.4, "environmental": 3.0, "financial": 2.8, "intellectual": 2.9, "occupational": 2.7, "physical": 3.4, "social": 1.8, "spiritual": 2.6}
jordan_pick = sugg(501, Item(id="ss-imleagues-pickleball-liv", kind="event", title="Intramural pickleball open play", dimensions=["physical", "social"]),
                   dt(2026, 10, 14, 19), dt(2026, 10, 14, 20), "Wed Oct 14, 7–8 PM", None,
                   Place(venue="Livingston Rec Center", address="62 Road 3, Piscataway, NJ 08854", lat=40.5249, lon=-74.4363, campus="new_brunswick"),
                   6, "free", "Free", 2, GoingCount(count=None, label="A few students are going"),
                   reasons(1.0, 1.0, 0.5, 1.0, 0.6, [F_CAMPUS, F_FREE], distance="6-minute walk",
                           texts={"dimension": "Social", "barrier": "Fits 'I don't know anyone'", "window": "Evening", "rung": "Structured", "helped_similar": "Rated 4+ by 60% of first-years"}),
                   "You already play: a game is the easiest way to meet people on Livingston.",
                   SourceRef(name="Rutgers Recreation via Scarlet Sync", url="https://recreation.rutgers.edu/"))
P["jordan"] = dict(campus="new_brunswick", sid="DEMO-JORDAN", t1=jordan_t1, focus="social", barriers=["dont_know_anyone", "not_my_scene"], windows=[], rung=2,
                   lang="en", pick=jordan_pick, alts=[andre_alts[1].model_copy(update={"rec_id": 502}), priya_alts[1].model_copy(update={"rec_id": 503})],
                   housing="resident", level="undergrad")


def write(persona, key, model):
    d = OUT / persona
    d.mkdir(parents=True, exist_ok=True)
    data = model.model_dump(mode="json") if hasattr(model, "model_dump") else model
    (d / f"{key}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def profile(p):
    return Profile(focus=p["focus"], barriers=p["barriers"], free_windows=p["windows"], social_rung=p["rung"], language=p["lang"])


def build():
    for key, p in P.items():
        campus = p["campus"]
        t1 = take(1, date(2026, 9, 14) if key == "andre" else date(2026, 10, 6), p["t1"])
        care = key == "taylor"
        s = p["t1"]
        strengths = [d for d in sorted(s, key=lambda d: -s[d]) if s[d] >= 3.0][:3] or [max(s, key=s.get)]
        write(key, "me_map", MapResponse(
            synthetic=True, now=NOW, student=StudentSummary(id=p["sid"], persona=key, campus=campus, level=p["level"], housing=p["housing"], language=p["lang"]),
            latest=t1, dimensions=dims(s), strengths=strengths, growth_areas=[d for d in s if s[d] < 2.3], care_first=care,
            previous_takes=[], profile=profile(p), retake_nudge=None))
        write(key, "me_focus", ProfileResult(synthetic=True, now=NOW, profile=profile(p)))
        write(key, "me_focus_crisis", crisis(campus))
        nxt = NextResponse(synthetic=True, now=NOW, set_id=f"set-{key}-1", care_first=care, support_card=p.get("care"),
                           pick=p["pick"], alternates=p["alts"], crisis_lines=lines(campus))
        write(key, "me_next", nxt)
        write(key, "me_next_after_decline", nxt.model_copy(update={"pick": (p["alts"] or [p["pick"]])[0], "alternates": (p["alts"][1:] + [p["pick"]]) if p["alts"] else [], "set_id": f"set-{key}-2"}))
        pk = p["pick"]
        write(key, "me_card", CardResponse(synthetic=True, now=NOW, kind="support" if care else "step",
                                           title=p["care"].title if care else pk.item.title, when_label=None if care else pk.when_label,
                                           line=p["care"].options[0].name if care else pk.why, deep_link="/next"))
        mem = [
            MemoryItem(id="profile:focus", kind="focus", statement=f"You chose to grow: {LABEL[p['focus']]}" if p["focus"] else "You haven't picked an area yet",
                       source=MemorySource(type="you_chose", label="Your choice", at=NOW), used_for="Picks steps for this area", learned_at=NOW),
        ] + [MemoryItem(id=f"profile:barrier:{b}", kind="barrier", statement=f"What gets in the way: {b.replace('_', ' ')}",
                        source=MemorySource(type="you_chose", label="You tapped this", at=NOW), used_for="Favours steps that get around it", learned_at=NOW)
             for b in p["barriers"]] + [MemoryItem(id=f"profile:window:{i}", kind="free_window", statement=f"Free: {w}",
                                                   source=MemorySource(type="you_chose", label="Your schedule", at=NOW), used_for="Only suggests things that fit", learned_at=NOW)
                                        for i, w in enumerate(p["windows"])]
        write(key, "me_memory", MemoryList(synthetic=True, now=NOW, items=mem))
        write(key, "delete_result", DeleteResult(synthetic=True, now=NOW, deleted=1))
        write(key, "me_inbox", InboxResponse(synthetic=True, now=NOW, items=[]))
        write(key, "session", SessionResponse(synthetic=True, now=NOW, token="fixture-token", persona=key, role="student", student_id=p["sid"]))
        write(key, "subscription", SubscriptionResult(synthetic=True, now=NOW, ok=True))
        if pk.starts_at:
            write(key, "commitment", CommitResponse(
                synthetic=True, now=NOW, commitment_id=9001, status="planned", item=pk.item, when_label=pk.when_label, where=pk.where,
                plan_text=f"When class ends on {pk.starts_at:%A} at 12:20, I walk to {pk.where.venue} for {pk.item.title.replace(' (sample)', '')}." if key == "andre"
                else f"On {pk.starts_at:%A} at {pk.starts_at.strftime('%I:%M %p').lstrip('0')}, I go to {pk.where.venue}.",
                plan_source="template", ics_url="/commitments/9001/ics?t=fixture-invite", google_calendar_url="https://calendar.google.com/calendar/render?action=TEMPLATE",
                reminder_at=pk.starts_at - timedelta(minutes=15), followup_at=pk.ends_at + timedelta(hours=2) if pk.ends_at else None,
                invite_url="/i/fixture-invite", invite_token="fixture-invite",
                share_text=f"I'm going to {pk.item.title} {pk.when_label}. Come with me?"))
        else:
            write(key, "commitment", CommitResponse(
                synthetic=True, now=NOW, commitment_id=9001, status="planned", item=pk.item, when_label=pk.when_label, where=pk.where,
                plan_text=f"This week, after my last class, I stop by {pk.item.title}.", plan_source="template",
                ics_url="/commitments/9001/ics?t=fixture-invite", google_calendar_url="https://calendar.google.com/calendar/render?action=TEMPLATE",
                reminder_at=None, followup_at=NOW + timedelta(days=3), invite_url="/i/fixture-invite", invite_token="fixture-invite",
                share_text=f"I'm going to {pk.item.title} this week. Come with me?"))
        learned = [MemoryItem(id="m:1", kind="likes_format", statement="You enjoyed game-based events",
                              source=MemorySource(type="rating", label="You rated Commuter lunch and board games 4/5", at=dt(2026, 10, 15, 9)),
                              used_for="Game-based events rank a little higher", learned_at=dt(2026, 10, 15, 9))] if key == "andre" else []
        write(key, "followup", FollowupResponse(
            synthetic=True, now=dt(2026, 10, 13, 15, 30), commitment_id=9001, status="went",
            progress=ProgressDelta(dimension=p["focus"] or "emotional", steps_this_month=1, message="One step taken this month. That counts."),
            arc=ArcStatus(status="mock", message="Wellness credit added to The Arc (demo)"),
            challenge=ChallengeProgress(challenge_id=f"ch-campus-cup-oct-{campus}", title="Scarlet Wellness Cup: steps this week", added=2 if key == "andre" else 1,
                                        progress=28 if key == "andre" else 103, goal=110 if campus == "newark" else 400, pct=0.25),
            next_rung=NextRung(rung=3, label=RUNG[3], message="That went well. Ready to try something a bit more open next week?") if key == "andre" else None,
            learned=learned, win_prompt=True))
        write(key, "pulse", PulseResponse(synthetic=True, now=NOW, challenges=challenges(campus), wins=wins(), retake_nudge=None))
        write(key, "win_accepted", WinAccepted(synthetic=True, now=NOW, kind="accepted", win_id="w-new", message="Posted. Thanks for sharing."))
        write(key, "win_crisis", crisis(campus))
        write(key, "same_here", SameHere(synthetic=True, now=NOW, win_id="w01", same_here=42))
        write(key, "skip_ahead", SkipAheadResponse(
            synthetic=True, now=dt(2026, 10, 13, 12, 15), previous_now=NOW,
            fired=[FiredNotification(id=1, kind="reminder", title=f"{pk.item.title.replace(' (sample)', '')} starts in 15 minutes",
                                     body=f"{pk.where.venue or 'See details'}. Tap for the plan.", deep_link="/plan/9001",
                                     send_at=dt(2026, 10, 13, 12, 15), delivered="push", commitment_id=9001)]))

    # staff + shared
    write("staff", "session", SessionResponse(synthetic=True, now=NOW, token="fixture-token", persona="staff", role="staff", student_id=None))
    write("staff", "skip_ahead", SkipAheadResponse(synthetic=True, now=NOW + timedelta(days=1), previous_now=NOW, fired=[]))
    sf = StaffFilters()
    funnel_rows = [
        FunnelRow(campus="new_brunswick", dimension="social", students=303, suggested=1650, committed=990, with_friend=210, attended=640, helped=430, commit_rate=0.6, attend_rate=0.646, helped_rate=0.672),
        FunnelRow(campus="newark", dimension="social", students=93, suggested=510, committed=300, with_friend=66, attended=190, helped=124, commit_rate=0.588, attend_rate=0.633, helped_rate=0.653),
        FunnelRow(campus="camden", dimension="financial", students=82, suggested=420, committed=230, with_friend=31, attended=140, helped=84, commit_rate=0.548, attend_rate=0.609, helped_rate=0.6),
    ]
    write("staff", "staff_funnel", FunnelResponse(synthetic=True, now=NOW, filters=sf, suppressed_groups=2, rows=funnel_rows, totals=None))
    write("staff", "staff_gaps", GapsResponse(synthetic=True, now=NOW, filters=sf, suppressed_groups=0, rows=[
        GapRow(campus="camden", dimension="financial", low_students=82, items=3, low_students_per_item=27.3),
        GapRow(campus="newark", dimension="financial", low_students=149, items=8, low_students_per_item=18.6),
        GapRow(campus="new_brunswick", dimension="financial", low_students=405, items=25, low_students_per_item=16.2),
        GapRow(campus="camden", dimension="social", low_students=61, items=9, low_students_per_item=6.8),
    ], headline="Camden has 27 students with low financial scores for every financial item listed there."))
    overlays = [
        CalendarOverlay(label="Classes begin", start=date(2026, 9, 1), end=date(2026, 9, 1), approximate=False, source="Rutgers academic calendar"),
        CalendarOverlay(label="Midterms (approximate)", start=date(2026, 10, 5), end=date(2026, 10, 30), approximate=True, source="Assumption: not on the registrar calendar"),
        CalendarOverlay(label="Thanksgiving recess", start=date(2026, 11, 26), end=date(2026, 11, 29), approximate=False, source="Rutgers academic calendar"),
        CalendarOverlay(label="Reading days", start=date(2026, 12, 11), end=date(2026, 12, 14), approximate=False, source="Rutgers academic calendar"),
        CalendarOverlay(label="Final exams", start=date(2026, 12, 15), end=date(2026, 12, 22), approximate=False, source="Rutgers academic calendar"),
    ]
    pts = []
    for i in range(16):
        wk = date(2026, 9, 7) + timedelta(weeks=i)
        dip = 0.2 if date(2026, 10, 5) <= wk <= date(2026, 10, 30) else (0.33 if wk >= date(2026, 12, 14) else 0.0)
        pts.append(WeeklyPoint(campus="new_brunswick", dimension="physical", week=wk, avg_score=round(2.85 - dip, 2), n=120))
    write("staff", "staff_weekly", WeeklyResponse(synthetic=True, now=NOW, filters=sf, suppressed_groups=0, points=pts, overlays=overlays))
    write("staff", "staff_dips", DipsResponse(synthetic=True, now=NOW, filters=sf, suppressed_groups=0, threshold=0.15, overlays=overlays, dips=[
        Dip(campus="new_brunswick", dimension="physical", week=date(2026, 10, 12), avg_score=2.63, trailing_avg=2.82, drop=0.19, n=118, overlay="Midterms (approximate)"),
        Dip(campus="new_brunswick", dimension="physical", week=date(2026, 12, 14), avg_score=2.5, trailing_avg=2.78, drop=0.28, n=131, overlay="Final exams"),
    ]))
    write("staff", "staff_retakes", RetakesResponse(synthetic=True, now=NOW, filters=sf, suppressed_groups=0, rows=[
        RetakeRow(campus="new_brunswick", users=600, users_retook=420, users_rate=0.70, non_users=400, non_users_retook=220, non_users_rate=0.55),
        RetakeRow(campus="newark", users=170, users_retook=121, users_rate=0.71, non_users=110, non_users_retook=59, non_users_rate=0.54),
        RetakeRow(campus="camden", users=110, users_retook=76, users_rate=0.69, non_users=75, non_users_retook=48, non_users_rate=0.64),
    ]))
    write("_shared", "personas", PersonasResponse(synthetic=True, now=NOW, personas=PERSONAS))
    write("_shared", "reset", ResetResponse(synthetic=True, now=NOW, ok=True, seconds=0.0))
    write("_shared", "invite", InviteView(synthetic=True, now=NOW, token="fixture-invite", item=lunch, when_label="Tue Oct 13, 12:30–1:30 PM",
                                         where=robeson, going=GoingCount(count=14, label="14 Newark students are going"), accepted=False))
    write("_shared", "invite_accepted", InviteAccepted(synthetic=True, now=NOW, token="fixture-invite", accepted=True,
                                                      ics_url="/commitments/9001/ics?t=fixture-invite", message="You're in. See you there."))


def challenges(campus):
    goal = {"new_brunswick": 400, "newark": 110, "camden": 70}[campus]
    prog = {"new_brunswick": 102, "newark": 26, "camden": 19}[campus]
    label = {"new_brunswick": "New Brunswick", "newark": "Newark", "camden": "Camden"}[campus]
    return [
        Challenge(id=f"ch-campus-cup-oct-{campus}", title="Scarlet Wellness Cup: steps this week", scope="campus", scope_label=label, dimension=None,
                  goal=goal, progress=prog, pct=round(prog / goal, 3), starts_on=date(2026, 10, 12), ends_on=date(2026, 10, 18),
                  rule="Cooperative: each campus races its own goal, sized to enrollment. No individual leaderboard.", yours=True, synthetic=True),
        Challenge(id="ch-sleep-week", title="Sleep Week: three wind-down nights", scope="all", scope_label="All campuses", dimension="physical",
                  goal=1500, progress=0, pct=0.0, starts_on=date(2026, 10, 19), ends_on=date(2026, 10, 25),
                  rule="Timed for midterms. Counts check-ins, not hours slept.", yours=True, synthetic=True),
    ]


def wins():
    data = [("w01", "intellectual", "new_brunswick", "Went to tutoring for the first time. Calc feels less impossible.", 41),
            ("w02", "social", "new_brunswick", "Brought my lab partner to game night. We stayed two hours.", 27),
            ("w03", "social", "newark", "Ate lunch on campus instead of in my car. Small thing, felt good.", 33)]
    return [Win(id=i, text=t, dimension=d, campus=c, same_here=n, created_at=dt(2026, 10, 9, 12), synthetic=True) for i, d, c, t, n in data]


if __name__ == "__main__":
    build()
    print("fixtures written to", OUT)
