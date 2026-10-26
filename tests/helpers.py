"""Shared test doubles: a scripted LLM client and event builders.

The real client streams from an OpenAI-compatible endpoint. Everything above
that boundary — the ReAct loop, tool batching, HITL wiring — can therefore be
exercised deterministically by replaying raw stream events.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from vibecli.types import Message


class ScriptedLlm:
    model_name = "scripted-model"
    provider_name = "scripted"
    max_context_window = 8_000

    def __init__(self, turns: list[list[dict[str, Any]]]):
        self.turns = turns
        self.calls = 0
        self.received: list[list[Message]] = []
        self.tool_snapshots: list[list[dict[str, Any]]] = []

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        *,
        system_prompt: str,
    ) -> AsyncIterator[dict[str, Any]]:
        self.received.append(list(messages))
        self.tool_snapshots.append(list(tools))
        index = min(self.calls, len(self.turns) - 1)
        self.calls += 1
        for event in self.turns[index]:
            yield event


def text_turn(text: str, *, stop_reason: str = "end_turn") -> list[dict[str, Any]]:
    return [
        {"type": "text_delta", "text": text},
        {"type": "usage", "usage": {"input_tokens": 10, "output_tokens": 5}},
        {"type": "message_end", "stop_reason": stop_reason},
    ]


def tool_turn(name: str, arguments: str, *, call_id: str = "call_1") -> list[dict[str, Any]]:
    return [
        {"type": "text_delta", "text": "Checking the file."},
        {
            "type": "tool_call_delta",
            "tool_call": {
                "index": 0,
                "id": call_id,
                "function": {"name": name, "arguments": arguments},
            },
        },
        {"type": "usage", "usage": {"input_tokens": 12, "output_tokens": 7}},
        {"type": "message_end", "stop_reason": "tool_use"},
    ]
