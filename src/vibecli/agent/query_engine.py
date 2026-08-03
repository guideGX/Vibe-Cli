from __future__ import annotations

import asyncio

from vibecli.agent.agent import Agent
from vibecli.agent.orchestrator import AgentOrchestrator
from vibecli.agent.plan_execute import PlanExecuteAgent
from vibecli.config import VibeCliConfig
from vibecli.llm.base import LlmClient
from vibecli.prompt import PromptAssembler
from vibecli.tools.registry import ToolRegistry
from vibecli.types import Message, QueryResult


class QueryEngine:
    def __init__(
        self,
        *,