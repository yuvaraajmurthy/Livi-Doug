"""Thin Bedrock Converse wrapper: hard timeouts, a circuit breaker per model, Guardrails, no retries inline."""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import boto3
from botocore.config import Config

from app.models.demo import HealthCheck
from config.settings import get_settings

log = logging.getLogger("compass.llm")
POOL = ThreadPoolExecutor(max_workers=16, thread_name_prefix="bedrock")


class ModelUnavailable(Exception):
    pass


class Breaker:
    """Open after 3 consecutive failures; stay open 60 s."""

    def __init__(self, threshold: int = 3, cooldown: float = 60.0):
        self.threshold, self.cooldown = threshold, cooldown
        self.fails: dict[str, int] = {}
        self.open_until: dict[str, float] = {}
        self.lock = threading.Lock()

    def allow(self, model: str) -> bool:
        return time.monotonic() >= self.open_until.get(model, 0)

    def ok(self, model: str) -> None:
        with self.lock:
            self.fails[model] = 0

    def fail(self, model: str) -> None:
        with self.lock:
            self.fails[model] = self.fails.get(model, 0) + 1
            if self.fails[model] >= self.threshold:
                self.open_until[model] = time.monotonic() + self.cooldown
                self.fails[model] = 0


BREAKER = Breaker()


@lru_cache(maxsize=8)
def _client(read_timeout: float):
    s = get_settings()
    cfg = Config(connect_timeout=min(2.0, read_timeout), read_timeout=read_timeout,
                 retries={"max_attempts": 1, "mode": "standard"}, max_pool_connections=32)
    return boto3.client("bedrock-runtime", region_name=s.aws_region, config=cfg)


def enabled() -> bool:
    s = get_settings()
    return s.bedrock_enabled and not s.force_templates


def converse(model: str, prompt: str, *, system: str | None = None, max_tokens: int = 300, timeout: float = 1.5,
             temperature: float | None = 0.2, extra: dict | None = None, guardrail: bool = True, purpose: str = "") -> str:
    """Return the text output or raise ModelUnavailable. Never logs the prompt or output."""
    if not enabled():
        raise ModelUnavailable("disabled")
    if not BREAKER.allow(model):
        raise ModelUnavailable("breaker open")
    s = get_settings()
    kw: dict = {
        "modelId": model,
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": max_tokens},
    }
    if temperature is not None and "xai." not in model and "gpt-oss" not in model:
        kw["inferenceConfig"]["temperature"] = temperature
    if system:
        kw["system"] = [{"text": system}]
    if extra:
        kw["additionalModelRequestFields"] = extra
    if guardrail and s.guardrail_id and "anthropic." in model:
        kw["guardrailConfig"] = {"guardrailIdentifier": s.guardrail_id, "guardrailVersion": s.guardrail_version}
    t = time.perf_counter()
    try:
        fut = POOL.submit(_client(timeout + 1.0).converse, **kw)
        r = fut.result(timeout=timeout)
    except Exception as exc:
        BREAKER.fail(model)
        log.info("model call failed", extra={"model": model, "purpose": purpose, "outcome": type(exc).__name__,
                                              "ms": round((time.perf_counter() - t) * 1000)})
        raise ModelUnavailable(type(exc).__name__) from exc
    BREAKER.ok(model)
    if r.get("stopReason") == "guardrail_intervened":
        log.info("guardrail intervened", extra={"model": model, "purpose": purpose, "outcome": "guardrail"})
        raise ModelUnavailable("guardrail")
    text = "".join(c.get("text", "") for c in r["output"]["message"]["content"] if "text" in c).strip()
    log.info("model call", extra={"model": model, "purpose": purpose, "outcome": "ok", "ms": round((time.perf_counter() - t) * 1000)})
    if not text:
        raise ModelUnavailable("empty")
    return text


def apply_guardrail(text: str, source: str = "INPUT", timeout: float = 1.5) -> bool:
    """True if the standalone guardrail blocks the text. False if allowed or unavailable."""
    s = get_settings()
    if not s.guardrail_id or not enabled():
        return False
    try:
        fut = POOL.submit(_client(timeout + 1.0).apply_guardrail, guardrailIdentifier=s.guardrail_id,
                          guardrailVersion=s.guardrail_version, source=source, content=[{"text": {"text": text}}])
        r = fut.result(timeout=timeout)
        return r.get("action") == "GUARDRAIL_INTERVENED"
    except Exception:
        return False


def ping() -> HealthCheck:
    s = get_settings()
    t = time.perf_counter()
    try:
        converse(s.model_fast, "Reply with: ok", max_tokens=5, timeout=3.0, guardrail=False, purpose="health")
        return HealthCheck(ok=True, latency_ms=round((time.perf_counter() - t) * 1000, 1))
    except ModelUnavailable as exc:
        return HealthCheck(ok=False, detail=str(exc))
