from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".java",
    ".kt",
    ".go",
    ".rs",
    ".md",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".xml",
    ".html",
    ".css",
    ".scss",
    ".sql",
    ".sh",
}

SKIP_DIRS = {".git", ".venv", "node_modules", "dist", "build", "target", "__pycache__"}


@dataclass(slots=True)
class CodeSearchResult:
    path: str
    line: int
    snippet: str


class CodeIndex:
    def __init__(self, root: str | Path, db_path: str | Path | None = None):
        self.root = Path(root).resolve()
        self.db_path = (
            Path(db_path).expanduser() if db_path else self.root / ".vibecli" / "code_index.sqlite3"
        )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def rebuild(self, path: str | Path | None = None) -> int:
        base = self._resolve(path or self.root)
        files = [base] if base.is_file() else list(self._iter_files(base))
        with self._connect() as conn:
            conn.execute("delete from code_chunks where root = ?", (str(self.root),))