from __future__ import annotations

from datetime import datetime
from pathlib import Path

from vibecli.config import VibeCliConfig
from vibecli.memory import MemoryManager
from vibecli.skill import SkillRegistry


class PromptAssembler:
    def __init__(
        self,
        config: VibeCliConfig,
        cwd: str,
        tool_names: list[str],
        model: str,
        provider: str,
    ):
        self.config = config
        self.cwd = str(Path(cwd).resolve())
        self.tool_names = tool_names
        self.model = model
        self.provider = provider

    def build(self) -> str:
        parts = [
            "You are VibeCLI, a powerful AI coding assistant running in a terminal.",
            f"Current time: {datetime.now().isoformat(timespec='seconds')}",
            f"Working directory: {self.cwd}",
            f"Model: {self.model} ({self.provider})",
            f"Available tools: {', '.join(self.tool_names)}",
            "",
            "Guidelines:",
            "- Be concise, direct, and implementation-oriented.",
            "- Use tools to inspect files, search code, and verify behavior when needed.",
            "- Prefer deterministic local tools before guessing.",
            "- When writing files, use write_file and keep changes scoped.",
            "- Preserve URLs and user-provided identifiers exactly unless a tool result proves "
            "otherwise.",
            "- Ask a clarifying question only when proceeding would be risky.",
        ]
        project_memory = self._project_memory()
        if project_memory:
            parts.extend(["", "Project memory:", project_memory])
        skill_index = SkillRegistry(self.cwd).index_text() if self.config.features.skill else ""
        if skill_index:
            parts.extend(["", skill_index])
        return "\n".join(parts)

    def _project_memory(self) -> str:
        memory_files = [
            Path(self.cwd) / "VIBE.md",
            Path(self.cwd) / ".vibecli" / "VIBE.md",
            Path(self.cwd) / "VIBE.local.md",
            Path(self.cwd) / ".vibecli" / "VIBE.local.md",
        ]