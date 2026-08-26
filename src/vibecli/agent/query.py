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