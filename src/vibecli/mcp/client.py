from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from pydantic import AnyUrl

from vibecli.mcp.config import McpServerSpec, load_mcp_server_specs
from vibecli.tools.base import Tool, ToolContext, ToolResult, object_schema


# mcp note: stdio + streamable-http transports (see commit history).
class McpClientManager:
    def __init__(self, project_root: str | Path):
        self.project_root = str(Path(project_root).resolve())
        self.specs = load_mcp_server_specs(self.project_root)
        self.last_errors: dict[str, str] = {}

    async def load_tools(self) -> list[Tool]:
        tools: list[Tool] = []
        self.last_errors.clear()
        for spec in self.specs.values():
            if not spec.enabled:
                continue
            try:
                tools.extend(await self._tools_for_server(spec))
                tools.extend(self._virtual_resource_tools(spec))
                tools.extend(self._virtual_prompt_tools(spec))
            except Exception as exc:  # noqa: BLE001 - keep broken MCP servers isolated
                self.last_errors[spec.name] = str(exc)
        return tools

    async def list_server_tools(self, spec: McpServerSpec) -> list[Any]:
        async with self._session(spec) as session:
            result = await session.list_tools()
            return list(result.tools)

    async def call_server_tool(
        self,
        spec: McpServerSpec,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        async with self._session(spec) as session:
            result = await session.call_tool(
                tool_name,
                arguments,
                read_timeout_seconds=timedelta(seconds=spec.timeout),
            )
        return ToolResult(content=_content_to_text(result.content), is_error=bool(result.isError))

    async def list_resources(self, spec: McpServerSpec) -> ToolResult:
        async with self._session(spec) as session:
            result = await session.list_resources()
        lines = [
            f"{resource.uri} {resource.name or ''} {resource.description or ''}".strip()
            for resource in result.resources
        ]
        return ToolResult("\n".join(lines) or "(no resources)")

    async def read_resource(self, spec: McpServerSpec, uri: str) -> ToolResult:
        async with self._session(spec) as session:
            result = await session.read_resource(AnyUrl(uri))
        return ToolResult(_content_to_text(result.contents))

    async def list_prompts(self, spec: McpServerSpec) -> ToolResult:
        async with self._session(spec) as session:
            result = await session.list_prompts()
        lines = [f"{prompt.name} {prompt.description or ''}".strip() for prompt in result.prompts]
        return ToolResult("\n".join(lines) or "(no prompts)")

    async def get_prompt(
        self,
        spec: McpServerSpec,
        name: str,
        arguments: dict[str, str] | None = None,
    ) -> ToolResult:
        async with self._session(spec) as session:
            result = await session.get_prompt(name, arguments or {})
        return ToolResult(_content_to_text(result.messages))

    async def _tools_for_server(self, spec: McpServerSpec) -> list[Tool]:
        remote_tools = await self.list_server_tools(spec)
        wrapped: list[Tool] = []
        for remote_tool in remote_tools:
            tool_name = str(remote_tool.name)
            local_name = f"mcp__{spec.name}__{tool_name}"
            schema = remote_tool.inputSchema or object_schema({})