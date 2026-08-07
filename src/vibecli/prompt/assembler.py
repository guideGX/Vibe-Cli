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
