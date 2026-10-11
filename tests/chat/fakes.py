"""A scripted Strands model: each call to stream() plays the next scripted turn (tool calls and/or text)."""
import json
from collections.abc import AsyncIterable
from typing import Any

from strands.models.model import Model


class ScriptedModel(Model):
    def __init__(self, turns: list[list[dict]]):
        """turns: each turn is a list of parts: {"text": "..."} or {"tool": name, "input": {...}}."""
        self.turns = list(turns)
        self.calls: list[dict] = []
        self.config: dict = {}

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> Any:
        return self.config

    def structured_output(self, *args, **kwargs):  # not used
        raise NotImplementedError

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs) -> AsyncIterable[dict]:
        self.calls.append({"messages": messages, "system_prompt": system_prompt,
                           "tools": [t["name"] for t in (tool_specs or [])]})
        parts = self.turns.pop(0) if self.turns else [{"text": "Okay."}]
        yield {"messageStart": {"role": "assistant"}}
        used_tool = False
        for i, p in enumerate(parts):
            if "tool" in p:
                used_tool = True
                yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": f"t{len(self.calls)}-{i}", "name": p["tool"]}}}}
                yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(p.get("input", {}))}}}}
                yield {"contentBlockStop": {}}
            else:
                for chunk in (p["text"][:20], p["text"][20:]):
                    if chunk:
                        yield {"contentBlockDelta": {"delta": {"text": chunk}}}
                yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "tool_use" if used_tool else "end_turn"}}


class FakeAWSClient:
    """Stands in for a boto3 client: each operation returns its canned response (or raises it) and is recorded."""
    def __init__(self, **responses):
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def __getattr__(self, op):
        def call(**kw):
            self.calls.append((op, kw))
            r = self.responses[op]
            if isinstance(r, Exception):
                raise r
            return r
        return call
