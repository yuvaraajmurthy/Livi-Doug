"""Live implementations are filled in task by task; until then NotLive serves the fixture."""
from app.routes._serve import NotLive


def __getattr__(name):
    def _not_live(*args, **kwargs):
        raise NotLive(name)
    return _not_live


def barrier_meta():
    from app.services.meta import barrier_meta as _bm
    return _bm()
