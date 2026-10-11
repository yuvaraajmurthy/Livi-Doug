"""python -m app.cli {migrate|seed|reset|ingest|serve}"""
import sys


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if cmd == "migrate":
        from app.db import connect_direct
        from db.migrate import migrate
        with connect_direct() as c:
            c.autocommit = True
            print("applied:", migrate(c))
    elif cmd in ("seed", "reset"):
        from app.db import connect_direct
        from db.seed import seed_all
        with connect_direct() as c:
            seed_all(c, kb=(cmd == "seed" or "--full" in sys.argv))
            c.commit()
        print(cmd, "done")
    elif cmd == "init":  # migrate + seed in one go (first deploy)
        from app.db import connect_direct
        from db.migrate import migrate
        from db.seed import seed_all
        with connect_direct() as c:
            c.autocommit = True
            print("applied:", migrate(c))
        with connect_direct() as c:
            seed_all(c, kb=True)
            c.commit()
        print("init done")
    elif cmd == "ingest":
        from ingest.run import run_all
        run_all()
    else:
        import uvicorn
        uvicorn.run("app.main:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
