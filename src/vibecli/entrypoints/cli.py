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
    if value:
        typer.echo(f"vibecli {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    prompt: Annotated[
        str | None,
        typer.Option("-p", "--prompt", help="Print mode: single prompt, non-interactive"),
    ] = None,
    model: Annotated[str | None, typer.Option("-m", "--model", help="Override model name")] = None,
    provider: Annotated[
        str | None,
        typer.Option("--provider", help="Override LLM provider"),
    ] = None,
    plain: Annotated[bool, typer.Option("--plain", help="Use plain text rendering")] = False,
    cwd: Annotated[Path | None, typer.Option("--cwd", help="Working directory")] = None,
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version"),
    ] = False,
) -> None:
    _ = version
    if ctx.invoked_subcommand is not None:
        return
    root = (cwd or Path.cwd()).resolve()
    overrides: dict = {}
    if provider or model or plain:
        overrides = {
            "llm": {"provider": provider, "model": model},
            "render_mode": "plain" if plain else None,
        }
    config = load_config(project_root=root, overrides=overrides)
    if plain:
        config.render_mode = "plain"
    if prompt is not None:
        asyncio.run(_run_prompt(prompt, str(root), config))
    else:
        asyncio.run(start_repl(str(root), config))


@app.command("doctor")
def doctor(