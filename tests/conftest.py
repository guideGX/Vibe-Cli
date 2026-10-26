from __future__ import annotations

from pathlib import Path

import pytest

from vibecli.config import VibeCliConfig


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``Path.home()`` at a throwaway directory.

    Snapshots, memory, audit logs and the task queue all resolve their state
    under the user home, so every test that touches them runs isolated.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    return home


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws


@pytest.fixture
def config() -> VibeCliConfig:
    cfg = VibeCliConfig()
    cfg.llm.api_key = "test-key"
    return cfg
