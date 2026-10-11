"""Demo reset: back to the exact start state. KB rows are kept (ingestion owns them); pins are re-applied.

  python -m db.reset          # people, history, clock, challenges, crisis lines
  python -m db.reset --full   # also reload the KB from seed files
"""
import sys

from app.db import connect_direct, pool
from db.seed import seed_all


def reset_demo(full: bool = False) -> None:
    with pool().connection() as c:
        seed_all(c, kb=full)


if __name__ == "__main__":
    with connect_direct() as c:
        seed_all(c, kb="--full" in sys.argv)
        c.commit()
    print("reset done")
