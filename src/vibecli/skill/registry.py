from __future__ import annotations

import json
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Skill:
    name: str
    description: str
    path: Path
    content: str
    source: str = "project"
    version: str = ""
    tags: list[str] = field(default_factory=list)
    enabled: bool = True

    @property
    def body(self) -> str:
        return _strip_frontmatter(self.content).strip()


class SkillContextBuffer:
    def __init__(self, limit: int = 3):
        self.limit = limit
        self._items: OrderedDict[str, str] = OrderedDict()

    def push(self, name: str | None, body: str | None) -> None:
        if not name or not body:
            return
        if name in self._items:
            del self._items[name]
        self._items[name] = body
        while len(self._items) > self.limit:
            self._items.popitem(last=False)

    def drain(self) -> str:
        if not self._items:
            return ""
        chunks = [
            f"## Loaded Skill: {name}\n{body.strip()}"
            for name, body in self._items.items()
            if body.strip()
        ]
        self._items.clear()
        return "\n\n".join(chunks)

    def clear(self) -> None:
        self._items.clear()

    def is_empty(self) -> bool:
        return not self._items

    def size(self) -> int:
        return len(self._items)


class SkillStateStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or Path.home() / ".vibecli" / "skills.json").expanduser()

    def disabled(self) -> set[str]:
        if not self.path.exists():
            return set()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return set()
        values = data.get("disabled") if isinstance(data, dict) else None
        if not isinstance(values, list):
            return set()
        return {str(item) for item in values if str(item).strip()}

    def disable(self, name: str) -> None:
        values = self.disabled()
        values.add(name)
        self._write(values)

    def enable(self, name: str) -> None:
        values = self.disabled()
        values.discard(name)
        self._write(values)

    def _write(self, disabled: set[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"disabled": sorted(disabled)}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


class SkillRegistry:
    """Load SKILL.md files from built-in, user, and project locations."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        builtin_root: str | Path | None = None,
        user_root: str | Path | None = None,
        state_store: SkillStateStore | None = None,
    ):
        self.project_root = Path(project_root).resolve()
        package_root = Path(__file__).resolve().parents[1]
        self.builtin_root = Path(builtin_root or package_root / "builtin_skills")
        self.user_root = Path(user_root or Path.home() / ".vibecli" / "skills")
        self.project_skill_root = self.project_root / ".vibecli" / "skills"
        self.state_store = state_store or SkillStateStore()
        self._skills: dict[str, Skill] | None = None

    def reload(self) -> None:
        self._skills = None

    def list(self) -> list[Skill]:
        return self.enabled_skills()
