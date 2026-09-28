from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(slots=True)
class TaskRecord:
    id: str
    prompt: str
    status: str
    created_at: str
    updated_at: str
    result: str | None = None
    error: str | None = None


class DurableTaskManager:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def add(self, prompt: str) -> str:
        task_id = _new_id("task")
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                insert into tasks(id, prompt, status, created_at, updated_at)
                values (?, ?, 'queued', ?, ?)
                """,
                (task_id, prompt, now, now),
            )
        return task_id

    def claim_next(self) -> TaskRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                select id, prompt, status, created_at, updated_at, result, error
                from tasks
                where status = 'queued'
                order by created_at
                limit 1
                """
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "update tasks set status = 'running', updated_at = ? where id = ?",
                (_now(), row[0]),