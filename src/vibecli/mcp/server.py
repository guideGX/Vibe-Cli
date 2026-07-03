from __future__ import annotations

import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from vibecli.config import load_config
from vibecli.tools import ToolRegistry, get_builtin_tools
from vibecli.tools.base import ToolContext


def _build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register_all(get_builtin_tools())
    return registry


def _tool_list(registry: ToolRegistry) -> list[dict[str, Any]]:
    tools = []
    for definition in registry.definitions():
        fn = definition["function"]
        tools.append(
            {
                "name": fn["name"],
                "description": fn["description"],
                "inputSchema": fn["parameters"],
            }
        )
    return tools


async def _handle_request(request: dict[str, Any], cwd: str) -> dict[str, Any]:
    registry = _build_registry()
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}
    if method in {"initialize", "notifications/initialized"}:
        return {"jsonrpc": "2.0", "id": request_id, "result": {"serverInfo": {"name": "vibecli"}}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": _tool_list(registry)}}