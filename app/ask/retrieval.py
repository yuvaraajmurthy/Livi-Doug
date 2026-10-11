"""Hybrid retrieval over the KB: Postgres full-text + pgvector (Cohere Embed v4, multilingual) fused with
reciprocal rank fusion. A few hundred items: no re-ranker needed. Keyword-only when embeddings are unavailable."""
import json
import logging

from app.llm.bedrock import POOL, _client, enabled
from config.settings import get_settings

log = logging.getLogger("compass.retrieval")
DIM = 1024


def embed(texts: list[str], kind: str = "search_document", timeout: float = 3.0) -> list[list[float]] | None:
    if not enabled() or not texts:
        return None
    body = json.dumps({"texts": [t[:2000] for t in texts], "input_type": kind, "embedding_types": ["float"],
                       "output_dimension": DIM, "truncate": "RIGHT"})
    try:
        fut = POOL.submit(_client(timeout + 1).invoke_model, modelId=get_settings().model_embed, body=body)
        r = json.loads(fut.result(timeout=timeout)["body"].read())
        e = r["embeddings"]
        return e["float"] if isinstance(e, dict) else e
    except Exception as exc:
        log.info("embed failed", extra={"outcome": type(exc).__name__})
        return None


def _vec(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def embed_pending(conn, batch: int = 64) -> dict:
    rows = conn.execute("""SELECT i.id, i.title, coalesce(i.summary, '') AS summary, coalesce(i.venue, '') AS venue,
                                  coalesce(string_agg(DISTINCT replace(t.tag, '_', ' '), ', '), '') AS tags
                           FROM kb_items i LEFT JOIN kb_tags t ON t.item_id = i.id
                           WHERE i.active AND i.embedding IS NULL AND i.kind <> 'micro' GROUP BY 1, 2, 3, 4 ORDER BY 1""").fetchall()
    done = 0
    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        vecs = embed([f"{r['title']}. {r['summary']} {r['venue']}. Topics: {r['tags']}" for r in chunk], timeout=20.0)
        if not vecs:
            break
        for r, v in zip(chunk, vecs):
            conn.execute("UPDATE kb_items SET embedding = %s::vector WHERE id = %s", (_vec(v), r["id"]))
            done += 1
    return {"candidates": len(rows), "embedded": done}


MAX_VECTOR_DISTANCE = 0.75  # calibrated: relevant hits <= 0.74, off-topic >= 0.77 (Cohere Embed v4)  # cosine distance; beyond this a vector-only hit is not relevant enough


def search(conn, query: str, campus: str, now_local, k: int = 5) -> tuple[list[dict], bool]:
    """Return up to k items (dicts) for the student's campus + online, upcoming or ongoing only."""
    filt = """active AND kind <> 'micro' AND campus IN (%(campus)s, 'online')
              AND (starts_at IS NULL OR coalesce(ends_at, starts_at + interval '1 hour') > %(now)s)"""
    args = {"q": query, "campus": campus, "now": now_local, "k": 20}
    kw = conn.execute(
        f"""SELECT id FROM kb_items WHERE {filt}
              AND to_tsvector('english', title || ' ' || coalesce(summary, '') || ' ' || coalesce(venue, '')) @@ websearch_to_tsquery('english', %(q)s)
            ORDER BY ts_rank(to_tsvector('english', title || ' ' || coalesce(summary, '')), websearch_to_tsquery('english', %(q)s)) DESC
            LIMIT %(k)s""", args).fetchall()
    ranks: dict[str, float] = {}
    for i, r in enumerate(kw):
        ranks[r["id"]] = ranks.get(r["id"], 0) + 1 / (60 + i)
    qv = embed([query], kind="search_query", timeout=1.2)
    if qv:
        vec = conn.execute(f"""SELECT id, embedding <=> %(v)s::vector AS d FROM kb_items WHERE {filt} AND embedding IS NOT NULL
                               ORDER BY embedding <=> %(v)s::vector LIMIT %(k)s""", {**args, "v": _vec(qv[0])}).fetchall()
        for i, r in enumerate(v for v in vec if v["d"] <= MAX_VECTOR_DISTANCE):
            ranks[r["id"]] = ranks.get(r["id"], 0) + 1 / (60 + i)
    ids = [i for i, _ in sorted(ranks.items(), key=lambda kv: (-kv[1], kv[0]))[:k]]
    if not ids:
        return [], bool(kw)
    rows = conn.execute("SELECT * FROM kb_items WHERE id = ANY(%s)", (ids,)).fetchall()
    by = {r["id"]: r for r in rows}
    return [by[i] for i in ids if i in by], bool(kw)
