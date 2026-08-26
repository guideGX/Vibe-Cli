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

