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


def write_chrome_devtools_config(
    *,
    scope_root: str | Path | None = None,
    browser_url: str | None = None,
    headless: bool = False,
    slim: bool = False,
    no_usage_statistics: bool = True,
) -> Path:
    root = Path(scope_root).resolve() if scope_root else Path.home()
    config_dir = root / ".vibecli"
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "mcp.json"
    data = _read_json(path) or {"mcpServers": {}}
    servers = data.setdefault("mcpServers", {})
    args = ["-y", "chrome-devtools-mcp@latest"]
    if no_usage_statistics:
        args.append("--no-usage-statistics")
    if slim:
        args.append("--slim")
    if headless:
        args.append("--headless")
    if browser_url:
        args.append(f"--browser-url={browser_url}")
    servers["chrome-devtools"] = {
        "type": "stdio",
        "command": "npx",
        "args": args,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None