from functools import lru_cache

import yaml

from app.models.student import BarrierMeta, BarrierOption
from config.settings import CONFIG_DIR


@lru_cache
def barriers_config() -> dict:
    return yaml.safe_load((CONFIG_DIR / "barriers.yaml").read_text(encoding="utf-8"))


def barrier_meta() -> BarrierMeta:
    cfg = barriers_config()
    return BarrierMeta(
        barriers=[BarrierOption(id=k, label=v["label"], label_es=v["label_es"]) for k, v in cfg["barriers"].items()],
        dimensions=cfg["dimensions"],
    )
