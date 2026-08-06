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
        agent.history = list(history or [])
        async for event in agent.run(message):
            yield event

    async def plan(self, message: str):
        agent = PlanExecuteAgent(
            llm_client=self.llm_client,
            tool_registry=self.tool_registry,
            config=self.config,
            cwd=self.cwd,
            approval_callback=self.approval_callback,
        )
        async for event in agent.run(message):
            yield event

    async def team(self, message: str):
        orchestrator = AgentOrchestrator(
            llm_client=self.llm_client,
            tool_registry=self.tool_registry,
            config=self.config,
            cwd=self.cwd,
            approval_callback=self.approval_callback,
        )
        async for event in orchestrator.run(message):
            yield event

    async def ask_complete_async(
        self,
        message: str,
        history: list[Message] | None = None,
    ) -> QueryResult:
        text = ""
        tokens = 0
        turns = 0
        async for event in self.ask(message, history):
            if event.get("type") == "text_delta":
                text += str(event.get("text") or "")
            elif event.get("type") == "error":
                raise event["error"]
            elif event.get("type") == "done":
                tokens = int(event.get("total_tokens") or 0)
                turns = int(event.get("total_turns") or 0)
        return QueryResult(text=text, total_tokens=tokens, turns=turns)

    async def plan_complete_async(self, message: str) -> QueryResult:
        return await self._complete_from_events(self.plan(message))

    async def team_complete_async(self, message: str) -> QueryResult:
        return await self._complete_from_events(self.team(message))