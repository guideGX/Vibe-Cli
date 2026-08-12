from __future__ import annotations

import json
import re
import time
from typing import Any

from vibecli.llm.base import LlmClient
from vibecli.plan.models import ExecutionPlan, Task, TaskType
from vibecli.types import Message

PLANNER_PROMPT = """You are VibeCLI's planner.
Create a compact executable DAG for the user's task.
Return only JSON with this shape:
{
  "summary": "short summary",
  "tasks": [
    {
      "id": "stable_source_id",
      "description": "concrete executable step",
      "type": "FILE_READ|FILE_WRITE|COMMAND|ANALYSIS|VERIFICATION",
      "dependencies": ["stable_source_id"]
    }
  ]
}
Use independent tasks when they can run in parallel.
"""


class Planner:
    def __init__(self, llm_client: LlmClient):
        self.llm_client = llm_client

    async def create_plan(self, goal: str) -> ExecutionPlan:
        if _is_simple_goal(goal):
            return _minimal_plan(goal)
        text = await _collect_text(
            self.llm_client,
            [Message(role="user", content=f"Please create an execution plan for:\n{goal}")],
            system_prompt=PLANNER_PROMPT,
        )
        return self.parse_plan(goal, text)

    async def replan(self, failed_plan: ExecutionPlan, failure_reason: str) -> ExecutionPlan:
        completed = "\n".join(
            f"- {task.id}: {task.description}"
            for task in failed_plan.all_tasks()
            if task.result and not task.error
        )
        return await self.create_plan(
            f"{failed_plan.goal}\nFailure reason: {failure_reason}\nCompleted tasks:\n{completed}"
        )

    def parse_plan(self, goal: str, plan_json: str) -> ExecutionPlan:
        data = _parse_json_object(plan_json)
        task_nodes = data.get("tasks") or data.get("steps") or []
        if not isinstance(task_nodes, list) or not task_nodes:
            raise ValueError("planner output did not contain a non-empty tasks/steps array")

        plan = ExecutionPlan(id=f"plan_{int(time.time() * 1000)}", goal=goal)
        plan.summary = str(data.get("summary") or "")
        id_mapping: dict[str, str] = {}

        for index, node in enumerate(task_nodes, start=1):
            if not isinstance(node, dict):