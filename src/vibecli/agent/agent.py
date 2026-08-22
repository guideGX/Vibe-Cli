from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any

from vibecli.config import VibeCliConfig
from vibecli.llm.base import LlmClient
from vibecli.skill import SkillContextBuffer
from vibecli.snapshot import SnapshotService
from vibecli.tools.registry import ToolRegistry
from vibecli.types import Message, QueryResult

from .query import query


class Agent:
    def __init__(
        self,
        *,
        llm_client: LlmClient,
        tool_registry: ToolRegistry,
        system_prompt: str,
        cwd: str,
        config: VibeCliConfig,
        approval_callback=None,
        max_turns: int = 20,
    ):
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.system_prompt = system_prompt
        self.cwd = cwd
        self.config = config
        self.approval_callback = approval_callback
        self.max_turns = max_turns
        self.history: list[Message] = []
        self.skill_context_buffer = SkillContextBuffer()

    async def run(self, message: str) -> AsyncIterator[dict[str, Any]]:
        snapshot = SnapshotService(self.cwd)
        with suppress(Exception):