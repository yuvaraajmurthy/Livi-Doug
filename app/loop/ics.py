"""Minimal iCalendar file for a plan."""
from datetime import datetime, timedelta, timezone


def _fmt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _esc(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace(";", "\;").replace(",", "\,").replace("\n", "\n")


def build(uid: str, title: str, start: datetime | None, end: datetime | None, location: str | None, description: str, now: datetime) -> str:
    start = start or now + timedelta(days=1)
    end = end or start + timedelta(hours=1)
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Compass//Rutgers Health Hack 2026//EN", "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT", f"UID:{uid}@compass", f"DTSTAMP:{_fmt(now)}", f"DTSTART:{_fmt(start)}", f"DTEND:{_fmt(end)}",
        f"SUMMARY:{_esc(title)}", f"LOCATION:{_esc(location or '')}", f"DESCRIPTION:{_esc(description)}",
        "BEGIN:VALARM", "TRIGGER:-PT15M", "ACTION:DISPLAY", f"DESCRIPTION:{_esc(title)}", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR",
    ]
    return "\r\n".join(lines) + "\r\n"


def google_url(title: str, start: datetime | None, end: datetime | None, location: str | None, details: str) -> str:
    from urllib.parse import urlencode
    q = {"action": "TEMPLATE", "text": title, "details": details, "location": location or ""}
    if start:
        q["dates"] = f"{_fmt(start)}/{_fmt(end or start + timedelta(hours=1))}"
    return "https://calendar.google.com/calendar/render?" + urlencode(q)
