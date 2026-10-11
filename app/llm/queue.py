"""Background wording worker: drains wording_queue a few items at a time, in parallel."""
from concurrent.futures import ThreadPoolExecutor

from app.db import conn
from app.llm import wording
from app.llm.bedrock import enabled

_EXEC = ThreadPoolExecutor(max_workers=4, thread_name_prefix="wording")


def _one(row: dict) -> None:
    with conn() as c:
        wording.process(c, row["key"], row["purpose"], row["lang"], row["facts"])


def tick(batch: int = 6) -> int:
    if not enabled():
        return 0
    with conn() as c:
        if not c.execute("SELECT pg_try_advisory_xact_lock(4242)").fetchone()["pg_try_advisory_xact_lock"]:
            return 0
        rows = c.execute(
            """UPDATE wording_queue SET attempts = attempts WHERE key IN (
                 SELECT key FROM wording_queue WHERE status = 'queued' ORDER BY created_at LIMIT %s FOR UPDATE SKIP LOCKED)
               RETURNING key, purpose, lang, facts""", (batch,)).fetchall()
    list(_EXEC.map(_one, rows))
    return len(rows)


def drain(max_rounds: int = 20) -> int:
    """Synchronous drain for pre-warming (reset / deploy)."""
    total = 0
    for _ in range(max_rounds):
        n = tick(batch=8)
        total += n
        if n == 0:
            break
    return total
