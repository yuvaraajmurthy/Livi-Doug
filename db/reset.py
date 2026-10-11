"""Demo reset: back to the exact start state. KB rows are kept (ingestion owns them); pins are re-applied.

  python -m db.reset          # people, history, clock, challenges, crisis lines
  python -m db.reset --full   # also reload the KB from seed files
"""
import sys

from app.db import connect_direct, pool
from db.seed import seed_all


def reset_demo(full: bool = False) -> None:
    """Pause background workers, then reload with a lock timeout and a few retries (never deadlock the demo)."""
    import time

    import psycopg

    from app.workers import PAUSE
    PAUSE.set()
    try:
        time.sleep(0.5)
        for attempt in range(4):
            try:
                with pool().connection() as c:
                    c.execute("SET lock_timeout = '8s'")
                    seed_all(c, kb=full)
                    c.execute("RESET lock_timeout")
                return
            except (psycopg.errors.DeadlockDetected, psycopg.errors.LockNotAvailable):
                if attempt == 3:
                    raise
                time.sleep(1.0 + attempt)
    finally:
        PAUSE.clear()


if __name__ == "__main__":
    with connect_direct() as c:
        seed_all(c, kb="--full" in sys.argv)
        c.commit()
    print("reset done")
