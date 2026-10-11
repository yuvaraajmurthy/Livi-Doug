"""Apply db/migrations/*.sql in order, once each. Usage: python -m db.migrate"""
from pathlib import Path

import psycopg

from app.db import connect_direct

MIGRATIONS = Path(__file__).resolve().parent / "migrations"


def migrate(conn: psycopg.Connection) -> list[str]:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
    done = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations").fetchall()}
    applied = []
    for f in sorted(MIGRATIONS.glob("*.sql")):
        if f.name in done:
            continue
        with conn.transaction():
            conn.execute(f.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (f.name,))
        applied.append(f.name)
    conn.commit()
    return applied


if __name__ == "__main__":
    with connect_direct() as c:
        c.autocommit = True
        print("applied:", migrate(c) or "nothing new")
