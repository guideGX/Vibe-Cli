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