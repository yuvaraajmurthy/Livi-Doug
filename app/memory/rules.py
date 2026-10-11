"""Memory writers. Rules on taps and ratings write almost everything; a model only maps typed barrier text
to a closed vocabulary. Upsert by (kind, key) = supersede in place. Bounded to MAX_FACTS."""
from datetime import datetime

from psycopg.types.json import Jsonb

MAX_FACTS = 25

FORMAT_STATEMENTS = {
    "games": ("You enjoyed game-based events", "Disfrutaste eventos con juegos", "Game-based events rank a little higher"),
    "sports": ("Sports and active games work for you", "Los deportes te funcionan", "Active events rank a little higher"),
    "food": ("Events with food worked for you", "Los eventos con comida te funcionaron", "Events with food rank a little higher"),
    "structured": ("You liked structured events", "Te gustaron los eventos estructurados", "Structured events rank a little higher"),
    "workshop": ("Workshops worked for you", "Los talleres te funcionaron", "Workshops rank a little higher"),
    "online": ("Online options worked for you", "Las opciones en línea te funcionaron", "Online options rank a little higher"),
    "tutoring": ("Tutoring helped you", "Las tutorías te ayudaron", "Tutoring ranks a little higher"),
}
CONSTRAINTS = {
    "works_evenings": ("You work most evenings", "Trabajas casi todas las noches", "Evening events rank lower"),
    "works_afternoons": ("You work most afternoons", "Trabajas casi todas las tardes", "Afternoon events rank lower"),
    "long_commute": ("You have a long commute", "Tienes un viaje largo", "Online and on-the-way options rank higher"),
    "caregiving": ("You care for family", "Cuidas a tu familia", "Short, flexible steps rank higher"),
    "no_car": ("You don't have a car", "No tienes carro", "Walkable and online options rank higher"),
}
DAY = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _bucket(dt: datetime) -> str:
    h = dt.hour
    return "morning" if h < 12 else ("midday" if h < 15 else ("afternoon" if h < 17 else "evening"))


def upsert(conn, student_id: str, kind: str, key: str, statement: str, statement_es: str | None, source_type: str,
           source_label: str, used_for: str, now: datetime, confidence: float = 0.7, ref: dict | None = None) -> int:
    row = conn.execute(
        """INSERT INTO student_memory (student_id, kind, key, statement, statement_es, source_type, source_label, source_ref,
                                       confidence, used_for, created_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (student_id, kind, key) DO UPDATE SET statement = EXCLUDED.statement, statement_es = EXCLUDED.statement_es,
             source_type = EXCLUDED.source_type, source_label = EXCLUDED.source_label, source_ref = EXCLUDED.source_ref,
             confidence = LEAST(1.0, GREATEST(student_memory.confidence, EXCLUDED.confidence) + 0.1), updated_at = EXCLUDED.updated_at
           RETURNING id""",
        (student_id, kind, key, statement, statement_es, source_type, source_label, Jsonb(ref or {}), confidence, used_for, now, now),
    ).fetchone()
    _enforce_cap(conn, student_id)
    return row["id"]


def _enforce_cap(conn, student_id: str) -> None:
    conn.execute(
        """DELETE FROM student_memory WHERE id IN (
             SELECT id FROM student_memory WHERE student_id = %s
             ORDER BY confidence DESC, updated_at DESC OFFSET %s)""", (student_id, MAX_FACTS))


def remove(conn, student_id: str, kind: str, key: str) -> None:
    conn.execute("DELETE FROM student_memory WHERE student_id = %s AND kind = %s AND key = %s", (student_id, kind, key))


def on_feedback(conn, student_id: str, item: dict, went: bool, helped: int | None, now: datetime) -> list[int]:
    """item: title, formats, starts_at (aware), series_key, causes."""
    if not went:
        return []
    ids = []
    title = item["title"].replace(" (sample)", "")
    label_rating = f"You rated {title} {helped}/5" if helped else f"You went to {title}"
    formats = [f for f in (item.get("formats") or []) if f in FORMAT_STATEMENTS]
    if helped is not None and helped >= 4:
        for f in formats[:2]:
            st, st_es, used = FORMAT_STATEMENTS[f]
            ids.append(upsert(conn, student_id, "likes_format", f, st, st_es, "rating", label_rating, used, now,
                              ref={"item_id": item["id"], "helped": helped}))
            remove(conn, student_id, "disliked_format", f)
        if "academic_workload" in (item.get("causes") or []):
            st, st_es, used = FORMAT_STATEMENTS["tutoring"]
            ids.append(upsert(conn, student_id, "helped", "academic_workload", st, st_es, "rating", label_rating, used, now))
    elif helped is not None and helped <= 2:
        for f in formats[:2]:
            # Contradiction: drop the positive fact rather than keep two opposite ones.
            remove(conn, student_id, "likes_format", f)
            ids.append(upsert(conn, student_id, "disliked_format", f, f"{f.capitalize()} events didn't click for you",
                              None, "rating", label_rating, f"{f.capitalize()} events rank a little lower", now, confidence=0.6))
    st_at = item.get("starts_at")
    if st_at is not None:
        d = st_at.weekday()
        b = _bucket(st_at)
        part_en = {"morning": "mornings", "midday": "midday", "afternoon": "afternoons", "evening": "evenings"}[b]
        part_es = {"morning": "las mañanas", "midday": "el mediodía", "afternoon": "las tardes", "evening": "las noches"}[b]
        ids.append(upsert(conn, student_id, "time_works", f"{DAY[d]}_{b}", f"{DAY_EN[d]} {part_en} work for you",
                          f"Los {DAY_ES[d]} a {part_es} te funcionan", "attendance", f"You went on {DAY_EN[d]}",
                          f"{DAY_EN[d]} {part_en} rank a little higher", now, confidence=0.6))
    return ids


def on_decline(conn, student_id: str, item: dict, now: datetime) -> int:
    title = item["title"].replace(" (sample)", "")
    return upsert(conn, student_id, "declined", item["id"], f"You passed on {title}", f"No te interesó {title}", "decline",
                  "You tapped Swap or Not now", "Won't be suggested again (delete this to undo)", now, confidence=0.9)


def on_constraints(conn, student_id: str, constraints: list[str], now: datetime) -> list[int]:
    ids = []
    for c in constraints:
        if c in CONSTRAINTS:
            st, st_es, used = CONSTRAINTS[c]
            ids.append(upsert(conn, student_id, "constraint", c, st, st_es, "your_words",
                              "From what you typed (the text itself is not kept)", used, now, confidence=0.7))
    return ids


def on_rung(conn, student_id: str, rung: int, now: datetime) -> int:
    labels = {2: ("Ready for structured events", "Listo para eventos estructurados"), 3: ("Ready for more open social events", "Listo para eventos sociales abiertos")}
    st, st_es = labels.get(rung, ("Starting with just-show-up events", "Empezando con eventos sencillos"))
    return upsert(conn, student_id, "rung", "current", st, st_es, "rating", "After a step you rated 4 or 5",
                  "Sets how social the next suggestion is", now, confidence=0.8)
