from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from vibecli.config import VibeCliConfig
from vibecli.image import parse_image_references
from vibecli.llm.base import LlmClient
from vibecli.tools.base import ToolContext
from vibecli.tools.executor import ToolExecutor
from vibecli.tools.registry import ToolRegistry
from vibecli.types import Message


async def query(
    *,
    llm_client: LlmClient,
    tool_registry: ToolRegistry,
    system_prompt: str,
    user_message: str,
    history: list[Message] | None,
    cwd: str,
    config: VibeCliConfig,
    approval_callback=None,
    skill_context_buffer=None,
    max_turns: int = 20,
) -> AsyncIterator[dict[str, Any]]:
    user_message = _prepend_skill_context(user_message, skill_context_buffer)
    messages = [
        *(history or []),
        Message(role="user", content=parse_image_references(user_message, cwd)),
    ]
    tool_definitions = tool_registry.definitions()
    executor = ToolExecutor(tool_registry)
    context = ToolContext(
        cwd=cwd,
        config=config,
        approval_callback=approval_callback,
        skill_context_buffer=skill_context_buffer,
    )

    total_tokens = 0
    turn = 0

    while turn < max_turns:
        turn += 1
        text = ""
        thinking = ""
        stop_reason = "end_turn"
        usage_input = 0
        usage_output = 0
        tool_states: dict[int, dict[str, Any]] = {}

        async for event in llm_client.chat(messages, tool_definitions, system_prompt=system_prompt):
            event_type = event.get("type")
            if event_type == "text_delta":
                delta = str(event.get("text") or "")
                text += delta
                yield {"type": "text_delta", "text": delta}
            elif event_type == "thinking_delta":
                delta = str(event.get("thinking") or "")
                thinking += delta
                yield {"type": "thinking_delta", "thinking": delta}
            elif event_type == "tool_call_delta":
                _merge_tool_delta(tool_states, event["tool_call"])
            elif event_type == "message_end":
                stop_reason = str(event.get("stop_reason") or "end_turn")
            elif event_type == "usage":
                usage = event.get("usage") or {}
                usage_input += int(usage.get("input_tokens") or 0)
                usage_output += int(usage.get("output_tokens") or 0)
                yield {"type": "usage", "usage": usage}
            elif event_type == "error":
                yield {"type": "error", "error": event["error"]}
                return

        total_tokens += usage_input + usage_output
        tool_calls = _finalize_tool_calls(tool_states)
        assistant_message = Message(role="assistant", content=text, tool_calls=tool_calls)
        if thinking and text:
            assistant_message.content = text
        elif thinking:
            assistant_message.content = ""
        messages.append(assistant_message)
        yield {"type": "turn_complete", "turn": turn, "stop_reason": stop_reason}
