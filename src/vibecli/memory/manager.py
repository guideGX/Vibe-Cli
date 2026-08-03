from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(slots=True)
class MemoryEntry:
    id: int
    scope: str
    content: str
    created_at: str


class MemoryManager:
    def __init__(self, db_path: str | Path, scope: str):
        self.db_path = Path(db_path).expanduser()
        self.scope = scope
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def save(self, content: str) -> int:
        created_at = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                "insert into memories(scope, content, created_at) values (?, ?, ?)",
                (self.scope, content.strip(), created_at),
            )
            return int(cursor.lastrowid)

    def list(self, limit: int = 20) -> list[MemoryEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                """