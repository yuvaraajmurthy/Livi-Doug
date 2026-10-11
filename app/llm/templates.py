"""Template wording: always available, never needs a model. Built only from engine facts. English and Spanish."""

BARRIER_PHRASE = {
    "en": {
        "no_time": "fits the time you actually have",
        "dont_know_anyone": "there's something to do, so you don't need to know anyone",
        "money": "it's free",
        "coursework": "it goes after what's eating your time",
        "not_my_scene": "it's low-key",
        "too_far": "it's close",
        "low_energy": "it's easy to drop into",
        "not_sure_where": "it's a simple place to start",
    },
    "es": {
        "no_time": "cabe en el tiempo que realmente tienes",
        "dont_know_anyone": "hay algo que hacer, así que no necesitas conocer a nadie",
        "money": "es gratis",
        "coursework": "ataca lo que te quita el tiempo",
        "not_my_scene": "es tranquilo",
        "too_far": "queda cerca",
        "low_energy": "es fácil llegar",
        "not_sure_where": "es un buen lugar para empezar",
    },
}


def why(f: dict, lang: str = "en") -> str:
    """f: title, window_label, walk_min, cost, barriers_hit, rung, root_cause, kind, online."""
    es = lang == "es"
    bits = []
    if f.get("root_cause"):
        bits.append("ataca lo que te está quitando el sueño" if es else "it goes after what's cutting into your sleep")
    if f.get("window_label"):
        bits.append("cabe en tu horario libre" if es else f.get("window_label")[0].lower() + f.get("window_label")[1:])
    if f.get("walk_min") is not None and f["walk_min"] <= 15:
        bits.append(f"queda a {f['walk_min']} minutos a pie" if es else f"it's a {f['walk_min']}-minute walk")
    if f.get("online"):
        bits.append("es en línea" if es else "it's online")
    if f.get("cost") == "free" and "money" not in (f.get("barriers_hit") or []):
        bits.append("es gratis" if es else "it's free")
    for b in (f.get("barriers_hit") or [])[:2]:
        p = BARRIER_PHRASE["es" if es else "en"].get(b)
        if p and p not in bits:
            bits.append(p)
    if not bits:
        bits.append("es un paso pequeño y concreto" if es else "it's one small, concrete step")
    bits = bits[:3]
    if es:
        body = ", ".join(bits[:-1]) + (" y " if len(bits) > 1 else "") + bits[-1]
        return body[0].upper() + body[1:] + "."
    body = ", ".join(bits[:-1]) + (", and " if len(bits) > 2 else (" and " if len(bits) == 2 else "")) + bits[-1]
    return body[0].upper() + body[1:] + "."


def plan(f: dict, lang: str = "en") -> str:
    """If-then plan. f: title, venue, weekday, start_label, window_start_label, kind."""
    es = lang == "es"
    title = f["title"].replace(" (sample)", "")
    venue = f.get("venue")
    if f.get("weekday") and f.get("window_start_label"):
        if es:
            return f"Cuando termine mi clase el {f['weekday_es']} a las {f['window_start_label']}, camino a {venue or 'la actividad'} para {title}."
        return f"When class ends on {f['weekday']} at {f['window_start_label']}, I walk to {venue or 'the event'} for {title}."
    if f.get("weekday") and f.get("start_label"):
        if es:
            return f"El {f['weekday_es']} a las {f['start_label']}, voy a {title}{' en ' + venue if venue else ''}."
        return f"On {f['weekday']} at {f['start_label']}, I head to {title}{' at ' + venue if venue else ''}."
    if es:
        return f"Esta semana, después de mi última clase, paso por {title}."
    return f"This week, after my last class, I stop by {title}."


def reminder(f: dict, care_first: bool = False, lang: str = "en") -> tuple[str, str]:
    title = f["title"].replace(" (sample)", "")
    if lang == "es":
        return (f"{title} empieza en 15 minutos", f"{f.get('venue') or 'Toca para ver el plan'}.")
    if care_first:
        return (f"{title} is coming up", "Only if you feel like it. Tap for details.")
    return (f"{title} starts in 15 minutes", f"{f.get('venue') or 'Tap for the plan'}.")


def followup(f: dict, lang: str = "en") -> tuple[str, str]:
    title = f["title"].replace(" (sample)", "")
    if lang == "es":
        return (f"¿Qué tal {title}?", "Dos toques: ¿fuiste? ¿te ayudó?")
    return (f"How was {title}?", "Two taps: did you go, and did it help?")
