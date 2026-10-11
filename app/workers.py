"""Background loops inside the API task: notification dispatcher and wording generator.

Each loop takes a Postgres advisory lock per tick so several API tasks never double-send.
"""
import logging
import threading

from config.settings import get_settings

log = logging.getLogger("compass.workers")

PAUSE = threading.Event()  # set while a demo reset rewrites the tables


class Loop:
    def __init__(self, name: str, interval: float, fn):
        self.name, self.interval, self.fn = name, interval, fn
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, name=name, daemon=True)

    def start(self) -> "Loop":
        self._t.start()
        return self

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            if PAUSE.is_set():
                continue
            try:
                self.fn()
            except Exception as exc:  # a loop must never die
                log.warning("worker tick failed", extra={"route_key": self.name, "err": type(exc).__name__})


def start_workers() -> list[Loop]:
    s = get_settings()
    loops: list[Loop] = []
    if s.run_dispatcher:
        from app.loop.notify import tick as dispatch_tick
        loops.append(Loop("dispatcher", s.dispatcher_interval_s, dispatch_tick).start())
    if s.run_wording_worker:
        from app.llm.queue import tick as wording_tick
        loops.append(Loop("wording", 5.0, wording_tick).start())
    return loops
