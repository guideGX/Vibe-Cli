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
            count = 0
            for file_path in files:
                rel = str(file_path.relative_to(self.root))
                try:
                    lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                except OSError:
                    continue
                for line_number, line in enumerate(lines, start=1):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    conn.execute(
                        """
                        insert into code_chunks(root, path, line, content)
                        values (?, ?, ?, ?)
                        """,
                        (str(self.root), rel, line_number, stripped),
                    )
                    count += 1
            return count

    def search(self, query: str, limit: int = 20) -> list[CodeSearchResult]:
        terms = [term.lower() for term in query.split() if term.strip()]
        if not terms:
            return []
        rows: list[tuple[str, int, str]]
        with self._connect() as conn:
            like = f"%{terms[0]}%"
            rows = conn.execute(
                """
                select path, line, content
                from code_chunks
                where root = ? and lower(content) like ?
                order by path, line
                limit 500
                """,
                (str(self.root), like),
            ).fetchall()