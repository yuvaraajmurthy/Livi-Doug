"""Connection pool. Sync psycopg on purpose: FastAPI runs sync routes in a thread pool, which
works identically on Windows dev machines and Linux containers, and boto3 is sync anyway."""
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from config.settings import get_settings

DB_ERRORS = (psycopg.OperationalError, psycopg.InterfaceError, TimeoutError)

_pool: ConnectionPool | None = None


def _kwargs() -> dict:
    # prepare_threshold=None: safe behind PgBouncer-style poolers (Neon, RDS Proxy).
    return {"row_factory": dict_row, "prepare_threshold": None}


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        s = get_settings()
        _pool = ConnectionPool(
            s.database_url, min_size=1, max_size=10, kwargs=_kwargs(), open=False,
            timeout=5, name="compass",
        )
        _pool.open(wait=False)
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def conn() -> Iterator[psycopg.Connection]:
    """A pooled connection in a transaction: commits on success, rolls back on error."""
    with pool().connection() as c:
        yield c


def connect_direct(url: str | None = None) -> psycopg.Connection:
    """Unpooled connection for CLI tasks (migrate, seed, reset, ingest)."""
    return psycopg.connect(url or get_settings().database_url, **_kwargs())
