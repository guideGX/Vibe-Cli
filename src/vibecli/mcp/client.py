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