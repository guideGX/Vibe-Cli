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
            plan = await self.planner.create_plan(message)
            yield {"type": "text_delta", "text": plan.summarize() + "\n\n"}
            async for event in self._execute_plan(plan):
                if event.get("type") == "usage":
                    usage = event.get("usage") or {}
                    total_tokens += int(usage.get("input_tokens") or 0)
                    total_tokens += int(usage.get("output_tokens") or 0)
                elif event.get("type") == "plan_task_done":
                    total_turns += int(event.get("turns") or 0)
                    continue
                elif event.get("type") == "text_delta":
                    final_text += str(event.get("text") or "")
                yield event
            self.history = [
                Message(role="user", content=message),
                Message(role="assistant", content=final_text),
            ]
        except Exception as exc:  # noqa: BLE001
            yield {"type": "error", "error": exc}
            return
        finally:
            with suppress(Exception):
                snapshot.create("post-turn")
        yield {
            "type": "done",
            "total_turns": total_turns,
            "total_tokens": total_tokens,
            "messages": self.history,
        }

    async def _execute_plan(self, plan: ExecutionPlan) -> AsyncIterator[dict[str, Any]]:
        yield {"type": "text_delta", "text": "Executing plan...\n\n"}
        plan.mark_started()
        while True:
            executable = _executable_tasks_in_order(plan)
            if not executable:
                break
            if len(executable) == 1:
                result = await self._execute_task(plan, executable[0])
                async for event in self._apply_task_result(result):
                    yield event
                continue
            yield {
                "type": "text_delta",
                "text": (
                    f"Running parallel batch: {', '.join(task.id for task in executable)}\n\n"
                ),
            }
            results = await asyncio.gather(
                *(self._execute_task(plan, task) for task in executable),
                return_exceptions=False,
            )
            for result in results:
                async for event in self._apply_task_result(result):
                    yield event

        if plan.has_failed():
            plan.mark_failed()
            yield {"type": "text_delta", "text": "Plan partially completed with failed tasks.\n\n"}
        elif plan.is_all_completed():
            plan.mark_completed()
            yield {"type": "text_delta", "text": _build_plan_result(plan)}
        else:
            plan.mark_failed()
            yield {
                "type": "text_delta",
                "text": "Plan stalled because dependencies were not satisfied.\n\n",