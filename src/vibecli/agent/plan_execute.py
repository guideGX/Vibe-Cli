from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from vibecli.agent.query import query
from vibecli.config import VibeCliConfig
from vibecli.llm.base import LlmClient
from vibecli.plan import ExecutionPlan, Planner, Task, TaskStatus
from vibecli.prompt import PromptAssembler
from vibecli.skill import SkillContextBuffer
from vibecli.snapshot import SnapshotService
from vibecli.tools.registry import ToolRegistry
from vibecli.types import Message


@dataclass(slots=True)
class TaskRunResult:
    task: Task
    text: str
    tokens: int
    turns: int
    error: Exception | None = None


class PlanExecuteAgent:
    def __init__(
        self,
        *,
        llm_client: LlmClient,
        tool_registry: ToolRegistry,
        config: VibeCliConfig,
        cwd: str,
        approval_callback=None,
        planner: Planner | None = None,
        max_task_turns: int = 8,
    ):
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.config = config
        self.cwd = cwd
        self.approval_callback = approval_callback
        self.planner = planner or Planner(llm_client)
        self.max_task_turns = max_task_turns
        self.history: list[Message] = []
        self.skill_context_buffer = SkillContextBuffer()

    async def run(self, message: str) -> AsyncIterator[dict[str, Any]]:
        snapshot = SnapshotService(self.cwd)
        with suppress(Exception):
            snapshot.create("pre-turn")
        total_tokens = 0
        total_turns = 0
        final_text = ""
        try:
            yield {"type": "text_delta", "text": f"Planning task: {message}\n\n"}