from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from vibecli.agent.query import query
from vibecli.config import VibeCliConfig
from vibecli.llm.base import LlmClient
from vibecli.prompt import PromptAssembler
from vibecli.skill import SkillContextBuffer
from vibecli.snapshot import SnapshotService
from vibecli.tools.registry import ToolRegistry
from vibecli.types import Message


class AgentRole(StrEnum):
    PLANNER = "PLANNER"
    WORKER = "WORKER"
    REVIEWER = "REVIEWER"


class AgentMessageType(StrEnum):
    TASK = "TASK"
    RESULT = "RESULT"
    FEEDBACK = "FEEDBACK"
    APPROVAL = "APPROVAL"
    REJECTION = "REJECTION"
    ERROR = "ERROR"


class StepStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(slots=True)
class AgentMessage:
    from_agent: str
    from_role: AgentRole | None
    content: str
    type: AgentMessageType

    @classmethod
    def task(cls, from_agent: str, content: str) -> AgentMessage:
        return cls(from_agent, None, content, AgentMessageType.TASK)

    @classmethod
    def result(cls, from_agent: str, role: AgentRole, content: str) -> AgentMessage:
        return cls(from_agent, role, content, AgentMessageType.RESULT)

    @classmethod
    def error(cls, from_agent: str, role: AgentRole, content: str) -> AgentMessage:
        return cls(from_agent, role, content, AgentMessageType.ERROR)


@dataclass(slots=True)
class ExecutionStep:
    id: str
    description: str
    type: str
    dependencies: list[str]
    result: str = ""
    status: StepStatus = StepStatus.PENDING

    def with_result(self, result: str) -> ExecutionStep:
        return replace(self, result=result, status=StepStatus.COMPLETED)

    def with_failed(self, result: str) -> ExecutionStep:
        return replace(self, result=result, status=StepStatus.FAILED)

    def started(self) -> ExecutionStep:
        return replace(self, status=StepStatus.RUNNING)


class SubAgent:
    def __init__(
        self,
        *,
        name: str,
        role: AgentRole,
        llm_client: LlmClient,
        tool_registry: ToolRegistry,
        config: VibeCliConfig,
        cwd: str,
        approval_callback=None,
        skill_context_buffer: SkillContextBuffer | None = None,
    ):
        self.name = name
        self.role = role