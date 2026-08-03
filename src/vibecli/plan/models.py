from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum


class TaskType(StrEnum):
    PLANNING = "PLANNING"
    FILE_READ = "FILE_READ"
    FILE_WRITE = "FILE_WRITE"
    COMMAND = "COMMAND"
    ANALYSIS = "ANALYSIS"
    VERIFICATION = "VERIFICATION"


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class PlanStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(slots=True)
class Task:
    id: str
    description: str
    type: TaskType = TaskType.ANALYSIS
    dependencies: list[str] = field(default_factory=list)
    dependents: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: str = ""
    error: str = ""
    start_time: float = 0.0
    end_time: float = 0.0

    def add_dependency(self, task_id: str) -> None:
        if task_id not in self.dependencies:
            self.dependencies.append(task_id)

    def add_dependent(self, task_id: str) -> None:
        if task_id not in self.dependents:
            self.dependents.append(task_id)

    def mark_started(self) -> None:
        self.status = TaskStatus.RUNNING
        self.start_time = time.time()

    def mark_completed(self, result: str) -> None:
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.end_time = time.time()

    def mark_failed(self, error: str) -> None:
        self.status = TaskStatus.FAILED
        self.error = error
        self.end_time = time.time()

    def mark_skipped(self) -> None:
        self.status = TaskStatus.SKIPPED
        self.end_time = time.time()

    def is_executable(self, all_tasks: dict[str, Task]) -> bool:
        if self.status != TaskStatus.PENDING:
            return False
        return all(
            dep_id in all_tasks and all_tasks[dep_id].status == TaskStatus.COMPLETED
            for dep_id in self.dependencies
        )


@dataclass(slots=True)
class ExecutionPlan:
    id: str
    goal: str
    tasks: dict[str, Task] = field(default_factory=dict)
    status: PlanStatus = PlanStatus.CREATED
    summary: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    _execution_order: list[str] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        self.tasks[task.id] = task
        for dep_id in task.dependencies:
            dep = self.tasks.get(dep_id)
            if dep:
                dep.add_dependent(task.id)
        for existing in self.tasks.values():
            if task.id in existing.dependencies:
                task.add_dependent(existing.id)
        self._execution_order.clear()

    def get_task(self, task_id: str) -> Task | None:
        return self.tasks.get(task_id)

    def all_tasks(self) -> list[Task]:
        return list(self.tasks.values())

    def root_tasks(self) -> list[Task]:
        return [task for task in self.tasks.values() if not task.dependencies]

    def executable_tasks(self) -> list[Task]: