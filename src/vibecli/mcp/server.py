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
    if method == "tools/call":
        name = params.get("name")
        tool = registry.get(str(name))
        if not tool:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"message": f'Tool "{name}" not found'},
            }
        config = load_config(project_root=cwd)
        config.policy.hitl_mode = "never"
        result = await tool.execute(
            params.get("arguments") or {},
            ToolContext(cwd=cwd, config=config),
        )
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": result.content}],
                "isError": result.is_error,
            },
        }
    return {"jsonrpc": "2.0", "id": request_id, "error": {"message": f"Unknown method: {method}"}}


async def serve_stdio(cwd: str | None = None) -> None:
    root = str(Path(cwd or ".").resolve())
    loop = asyncio.get_running_loop()
    while True:
        line = await loop.run_in_executor(None, input)