from __future__ import annotations

import asyncio
from pathlib import Path

from vibecli.config import load_config
from vibecli.skill import SkillContextBuffer, SkillRegistry, SkillStateStore
from vibecli.tools.base import ToolContext
from vibecli.tools.builtins import load_skill


def test_skill_registry_layers_and_state(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    builtin = tmp_path / "builtin"
    user = tmp_path / "user"
    project = tmp_path / "project"
    _write_skill(builtin, "web-access", "builtin desc", "v0")
    _write_skill(user, "web-access", "user desc", "v1")
    _write_skill(project / ".vibecli" / "skills", "project-only", "project desc", "v2")