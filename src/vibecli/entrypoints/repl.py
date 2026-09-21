from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from vibecli import __version__
from vibecli.agent import Agent, AgentOrchestrator, PlanExecuteAgent
from vibecli.bootstrap import build_tool_registry
from vibecli.config import VibeCliConfig, config_to_public_dict
from vibecli.llm import create_llm_client
from vibecli.memory import MemoryManager
from vibecli.policy import AuditLog
from vibecli.prompt import PromptAssembler
from vibecli.rag import CodeIndex
from vibecli.render import RichRenderer
from vibecli.runtime import DurableTaskManager
from vibecli.skill import SkillRegistry
from vibecli.snapshot import SnapshotService
from vibecli.tools import ToolRegistry

SLASH_COMMANDS = [
    "/help",
    "/exit",
    "/clear",
    "/context",
    "/memory",
    "/save",
    "/config",
    "/tools",
    "/hitl",
    "/policy",
    "/audit",
    "/index",
    "/search",
    "/plan",
    "/team",
    "/model",
    "/skill",
    "/mcp",
    "/task",
    "/snapshot",
    "/restore",
]


async def start_repl(cwd: str, config: VibeCliConfig) -> None:
    console = Console()
    registry, mcp_manager = await build_tool_registry(config=config, cwd=cwd)
    client = create_llm_client(config.llm)
    system_prompt = PromptAssembler(
        config=config,
        cwd=cwd,
        tool_names=registry.list_names(),
        model=client.model_name,
        provider=client.provider_name,
    ).build()
    tool_count = len(registry.list_names())
    mcp_server_count = _count_mcp_servers(mcp_manager)
    skill_count = len(SkillRegistry(cwd).list())
    agents_file_count = _count_named_files(cwd, "AGENTS.md")
    renderer = RichRenderer(context_window=client.max_context_window)
    renderer.banner(
        model=client.model_name,
        provider=client.provider_name,
        cwd=cwd,
        tools=tool_count,
        version=__version__,
        api_key_configured=bool(config.llm.api_key),
        mcp_servers=mcp_server_count,
        skills=skill_count,
        agents_files=agents_file_count,
        hitl_mode=config.policy.hitl_mode,
    )
    agent = Agent(
        llm_client=client,
        tool_registry=registry,
        system_prompt=system_prompt,
        cwd=cwd,
        config=config,
        approval_callback=lambda request: _approval_prompt(request, console, config),
    )