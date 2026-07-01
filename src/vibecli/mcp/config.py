from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class McpServerSpec:
    name: str
    type: str = "stdio"
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    timeout: float = 30.0


def load_mcp_server_specs(project_root: str | Path) -> dict[str, McpServerSpec]:
    root = Path(project_root).resolve()
    merged: dict[str, Any] = {}
    for path in [Path.home() / ".vibecli" / "mcp.json", root / ".vibecli" / "mcp.json"]:
        data = _read_json(path)
        if not data:
            continue
        servers = data.get("mcpServers", data)
        if isinstance(servers, dict):
            merged.update(servers)
    return {
        name: _spec_from_raw(name, raw, root)
        for name, raw in merged.items()
        if isinstance(raw, dict)
    }

