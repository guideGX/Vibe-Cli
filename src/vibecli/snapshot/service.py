from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "node_modules", "dist", "build", "target", "__pycache__"}


@dataclass(slots=True)
class SnapshotRecord:
    id: str
    phase: str
    created_at: str
    path: Path


class SnapshotService:
    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).resolve()
        digest = hashlib.sha256(str(self.project_root).encode("utf-8")).hexdigest()[:16]
        self.root = Path.home() / ".vibecli" / "snapshots" / digest
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.jsonl"

    def create(self, phase: str) -> SnapshotRecord:
        snapshot_id = f"{phase}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"
        target = self.root / snapshot_id
        target.mkdir(parents=True, exist_ok=True)
        self._copy_tree(self.project_root, target)
        record = SnapshotRecord(
            id=snapshot_id,
            phase=phase,
            created_at=datetime.now(UTC).isoformat(),
            path=target,
        )
        with self.index_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "id": record.id,