from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from vibecli.config import VibeCliConfig

DangerLevel = Literal["safe", "medium", "high"]
ToolDecision = Literal["approve", "deny", "skip"]


@dataclass(slots=True)
class ToolResult:
    content: str
    is_error: bool = False
    display_summary: str | None = None
    tool_use_id: str | None = None


@dataclass(slots=True)
class ToolContext:
    cwd: str
    config: VibeCliConfig
    approval_callback: Callable[[dict[str, Any]], Awaitable[ToolDecision] | ToolDecision] | None = (
        None
    )
    skill_context_buffer: Any | None = None


@dataclass(slots=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any], ToolContext], Awaitable[ToolResult]]
    is_read_only: bool = True
    is_concurrency_safe: bool = True
    danger_level: DangerLevel = "safe"
    requires_approval: bool = False
    timeout: float = 60.0