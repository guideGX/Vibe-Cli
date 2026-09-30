from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from vibecli import __version__
from vibecli.agent import QueryEngine
from vibecli.bootstrap import build_tool_registry
from vibecli.config import get_config_paths, load_config
from vibecli.entrypoints.repl import start_repl
from vibecli.llm import create_llm_client
from vibecli.mcp import load_mcp_server_specs, serve_http, serve_stdio, write_chrome_devtools_config
from vibecli.runtime import RuntimeApiServer
from vibecli.runtime.api import runtime_api_key

app = typer.Typer(
    name="vibecli",
    help="VibeCLI — Terminal AI Agent in Python",
    invoke_without_command=True,
    no_args_is_help=False,
)
mcp_app = typer.Typer(help="MCP server management")
app.add_typer(mcp_app, name="mcp")
console = Console()


def _version_callback(value: bool) -> None: