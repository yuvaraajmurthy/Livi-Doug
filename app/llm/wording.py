"""Wording: cache hit -> AI line; miss -> template now and generation queued. Never waits on a model inline.

Generation order: Grok 4.7 (reasoning effort low) -> Claude Haiku 4.5 -> keep the template.
Every candidate must pass the grounding check. Cache keys hash the facts, never a student id.
"""
import hashlib
import json
import logging

from psycopg.types.json import Jsonb

from app.llm import grounding, templates
from app.llm.bedrock import ModelUnavailable, converse
from config.settings import get_settings

log = logging.getLogger("compass.wording")

SYSTEM = {
    ("why", "en"): """You write one short, warm, friend-like sentence (at most 25 words) telling a university student why one
suggested next step fits them. Use ONLY the facts in the JSON. Never add a time, day, date, number, price, place, name or
claim that is not in the facts. Never mention scores, moods, struggles, health, or anything clinical. No emojis, no quotes,
no greeting. Output the sentence only.""",
    ("why", "es"): """Escribe una sola oración breve, cálida y cercana (máximo 25 palabras) que le diga a un estudiante
universitario por qué este paso le conviene. Usa SOLO los datos del JSON. No agregues horas, días, fechas, números, precios,
lugares, nombres ni afirmaciones que no estén en los datos. No menciones puntajes, estados de ánimo, problemas ni nada
clínico. Sin emojis ni comillas. Responde solo con la oración.""",
    ("plan", "en"): """Rewrite the draft if-then plan as one natural first-person sentence (at most 30 words) a student would
actually say to themselves, keeping the "When ..., I ..." shape. Keep every fact from the draft and add nothing: no new times,
days, places or details. No emojis, no quotes. Output the sentence only.""",
    ("plan", "es"): """Reescribe el borrador del plan "si-entonces" como una sola oración natural en primera persona (máximo 30
palabras), con la forma "Cuando ..., yo ...". Conserva todos los datos del borrador y no agregues nada: ni horas, ni días, ni
lugares, ni detalles nuevos. Sin emojis ni comillas. Responde solo con la oración.""",
}


def key(purpose: str, lang: str, facts: dict) -> str:
    raw = json.dumps({"p": purpose, "l": lang, "f": facts}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def template(purpose: str, facts: dict, lang: str) -> str:
    return templates.why(facts, lang) if purpose == "why" else templates.plan(facts, lang)


def get(conn, purpose: str, facts: dict, lang: str = "en", enqueue: bool = True) -> tuple[str, str]:
    """(text, source) where source is 'ai' or 'template'."""
    k = key(purpose, lang, facts)
    if not get_settings().force_templates:
        hit = conn.execute("SELECT text FROM llm_cache WHERE key = %s", (k,)).fetchone()
        if hit:
            return hit["text"], "ai"
    if enqueue:
        conn.execute("INSERT INTO wording_queue (key, purpose, lang, facts) VALUES (%s, %s, %s, %s) ON CONFLICT (key) DO NOTHING",
                     (k, purpose, lang, Jsonb(facts)))
    return template(purpose, facts, lang), "template"


def generate(purpose: str, facts: dict, lang: str) -> tuple[str, str] | None:
    """Try models in order; return (text, model) for the first grounded output, else None."""
    s = get_settings()
    if purpose == "plan":
        facts = {**facts, "draft": templates.plan(facts, lang)}
    prompt = "Facts (JSON):\n" + json.dumps(facts, ensure_ascii=False, default=str)
    attempts = [
        (s.model_wording, dict(max_tokens=1500, timeout=s.wording_timeout_s, temperature=None, extra={"reasoning": {"effort": "low"}})),
        (s.model_wording_fallback, dict(max_tokens=120, timeout=4.0, temperature=0.4)),
    ]
    for model, kw in attempts:
        try:
            text = converse(model, prompt, system=SYSTEM[(purpose, lang)], purpose=f"wording_{purpose}", **kw)
        except ModelUnavailable:
            continue
        text = text.strip().strip('"').strip()
        issues = grounding.check(text, facts, lang, max_words=32 if purpose == "why" else 40)
        if not issues:
            return text, model
        log.info("wording rejected", extra={"model": model, "purpose": purpose, "outcome": ",".join(issues)[:120]})
    return None


def process(conn, k: str, purpose: str, lang: str, facts: dict) -> bool:
    res = generate(purpose, facts, lang)
    if res:
        conn.execute("INSERT INTO llm_cache (key, purpose, lang, model, text) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (key) DO NOTHING",
                     (k, purpose, lang, res[1], res[0]))
        conn.execute("UPDATE wording_queue SET status = 'done' WHERE key = %s", (k,))
        return True
    conn.execute("UPDATE wording_queue SET attempts = attempts + 1, status = CASE WHEN attempts >= 1 THEN 'failed' ELSE 'queued' END WHERE key = %s", (k,))
    return False
