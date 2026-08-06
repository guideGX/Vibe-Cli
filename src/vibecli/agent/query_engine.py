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
        llm_client: LlmClient,
        tool_registry: ToolRegistry,
        config: VibeCliConfig,
        cwd: str,
        approval_callback=None,
    ):
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.config = config
        self.cwd = cwd
        self.approval_callback = approval_callback
        self.system_prompt = PromptAssembler(
            config=config,
            cwd=cwd,
            tool_names=tool_registry.list_names(),
            model=llm_client.model_name,
            provider=llm_client.provider_name,
        ).build()

    async def ask(self, message: str, history: list[Message] | None = None):
        agent = Agent(
            llm_client=self.llm_client,
            tool_registry=self.tool_registry,
            system_prompt=self.system_prompt,
            cwd=self.cwd,
            config=self.config,
            approval_callback=self.approval_callback,
        )