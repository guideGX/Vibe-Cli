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

    history_path = Path.home() / ".vibecli" / "history" / "prompt_history.txt"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    session = PromptSession(
        message=lambda: _prompt_message(
            cwd=cwd,
            model=client.model_name,
            tools=tool_count,
            agents_files=agents_file_count,
            mcp_servers=mcp_server_count,
            skills=skill_count,
            stats=renderer.toolbar_status(),
        ),
        history=FileHistory(str(history_path)),
        completer=WordCompleter(SLASH_COMMANDS, ignore_case=True),
        placeholder=[("class:placeholder", "Type your message or @path/to/file")],
        style=Style.from_dict(
            {
                "prompt": "bold #ffffff bg:#262626",
                "placeholder": "#9a9a9a bg:#262626",
                "prompt.dim": "#a3a3a3 bg:#000000",
                "prompt.count.agents": "bold #22d3ee bg:#000000",
                "prompt.count.mcp": "bold #c084fc bg:#000000",
                "prompt.count.skills": "bold #facc15 bg:#000000",
                "prompt.tools": "bold #22d3ee bg:#000000",
                "toolbar.model": "noreverse bold #ffffff bg:#000000",
                "toolbar.ctx.bar": "noreverse #22c55e bg:#000000",
                "toolbar.ctx.value": "noreverse #ffffff bg:#000000",
                "toolbar.cwd.value": "noreverse #c084fc bg:#000000",
                "toolbar.gap": "noreverse #ffffff bg:#000000",
            }
        ),
    )

    while True:
        try:
            user_input = await session.prompt_async()
        except (EOFError, KeyboardInterrupt):
            console.print()
            return
        message = user_input.strip()
        if not message:
            continue
        if message.startswith("/"):
            should_exit = await _handle_slash(message, console, cwd, config, agent, registry)
            if should_exit:
                return
            continue
        await _run_agent(agent, renderer, message)


async def _run_agent(agent: Agent, renderer: RichRenderer, message: str) -> None:
    await _run_events(agent.run(message), renderer, agent.llm_client.max_context_window)


async def _run_events(events, renderer: RichRenderer, context_window: int | None = None) -> None:
    renderer.set_context_window(context_window)
    renderer.start_run()
    renderer.newline()
    async for event in events:
        renderer.handle(event)
        if event.get("type") == "error":
            break
    renderer.newline()


async def _handle_slash(
    raw: str,
    console: Console,
    cwd: str,
    config: VibeCliConfig,
    agent: Agent,
    registry: ToolRegistry,
) -> bool:
    command, _, rest = raw.partition(" ")
    arg = rest.strip()
    if command in {"/exit", "/quit"}:
        return True
    if command == "/help":
        console.print("\n".join(SLASH_COMMANDS))
    elif command == "/clear":
        agent.clear_history()
        console.clear()
    elif command == "/context":
        memories = MemoryManager(config.memory.long_term_db_path, scope=cwd).list(limit=5)
        table = Table(title="VibeCLI Context")
        table.add_column("Field")
        table.add_column("Value")
        table.add_row("cwd", cwd)
        table.add_row("model", f"{config.llm.model} ({config.llm.provider})")
        table.add_row("context window", str(agent.llm_client.max_context_window))
        table.add_row("render", config.render_mode)
        table.add_row("memory", f"{len(memories)} recent entries")
        table.add_row("tools", str(len(registry.list_names())))
        console.print(table)
    elif command == "/memory":
        await _memory_command(arg, console, cwd, config)
    elif command == "/save":
        if not arg:
            console.print("[red]Usage:[/red] /save <fact>")
        else:
            memory_id = MemoryManager(config.memory.long_term_db_path, scope=cwd).save(arg)
            console.print(f"Saved memory #{memory_id}")
    elif command == "/config":
        console.print_json(json.dumps(config_to_public_dict(config), ensure_ascii=False))
    elif command == "/tools":
        console.print("\n".join(registry.list_names()))
    elif command == "/hitl":
        _hitl_command(arg, console, config)
    elif command == "/policy":
        console.print_json(json.dumps(config_to_public_dict(config)["policy"], ensure_ascii=False))
    elif command == "/audit":
        limit = int(arg or "20") if (arg or "20").isdigit() else 20
        console.print_json(
            json.dumps(AuditLog(config.policy.audit_log_path).tail(limit), ensure_ascii=False)
        )
    elif command == "/index":
        count = CodeIndex(cwd).rebuild(arg or ".")
        console.print(f"Indexed {count} code lines.")
    elif command == "/search":
        results = CodeIndex(cwd).search(arg, limit=20)
        output = "\n".join(f"{r.path}:{r.line}: {r.snippet}" for r in results)
        console.print(output or "(no matches)")
    elif command == "/plan":
        if not arg:
            console.print("[red]Usage:[/red] /plan <task>")
        else:
            plan_agent = PlanExecuteAgent(
                llm_client=agent.llm_client,
                tool_registry=registry,
                config=config,
                cwd=cwd,
                approval_callback=agent.approval_callback,
            )
            await _run_events(
                plan_agent.run(arg),
                RichRenderer(),
                agent.llm_client.max_context_window,
            )
    elif command == "/team":
        if not arg:
            console.print("[red]Usage:[/red] /team <task>")
        else:
            orchestrator = AgentOrchestrator(
                llm_client=agent.llm_client,
                tool_registry=registry,
                config=config,
                cwd=cwd,
                approval_callback=agent.approval_callback,
            )
            await _run_events(
                orchestrator.run(arg),
                RichRenderer(),
                agent.llm_client.max_context_window,
            )
    elif command == "/model":
        _model_command(arg, console, config)
    elif command == "/skill":
        _skill_command(arg, console, cwd)
    elif command == "/mcp":
        console.print("Use `vibecli mcp serve --transport stdio|http --port 3000` to expose tools.")
    elif command == "/task":
        _task_command(arg, console)
    elif command == "/snapshot":
        _snapshot_command(arg, console, cwd)
    elif command == "/restore":
        if not arg:
            console.print("[red]Usage:[/red] /restore <snapshot-id-or-index>")
        else:
            record = SnapshotService(cwd).restore(arg)
            console.print(f"Restored {record.id}")
    else:
        console.print(f"[red]Unknown command:[/red] {command}")
    return False


async def _memory_command(arg: str, console: Console, cwd: str, config: VibeCliConfig) -> None:
    manager = MemoryManager(config.memory.long_term_db_path, scope=cwd)
    sub, _, rest = arg.partition(" ")
    if sub == "clear":
        count = manager.clear()
        console.print(f"Cleared {count} memories.")
    elif sub == "search":
        rows = manager.search(rest)
        console.print("\n".join(f"#{row.id} {row.content}" for row in rows) or "(no matches)")
    else:
        rows = manager.list()
        console.print("\n".join(f"#{row.id} {row.content}" for row in rows) or "(no memories)")


def _hitl_command(arg: str, console: Console, config: VibeCliConfig) -> None:
    if arg in {"always", "auto", "never"}:
        config.policy.hitl_mode = arg
    elif arg == "on":
        config.policy.hitl_mode = "always"
    elif arg == "off":
        config.policy.hitl_mode = "never"
    console.print(f"HITL mode: {config.policy.hitl_mode}")


def _model_command(arg: str, console: Console, config: VibeCliConfig) -> None:
    if not arg:
        console.print(f"{config.llm.model} ({config.llm.provider})")
        return
    parts = arg.split()
    if len(parts) == 1:
        config.llm.model = parts[0]
    else:
        config.llm.provider = parts[0]
        config.llm.model = parts[1]
    console.print(
        "Model updated for newly created clients. Restart REPL to rebuild the active client."
    )


def _skill_command(arg: str, console: Console, cwd: str) -> None:
    registry = SkillRegistry(cwd)
    sub, _, rest = arg.partition(" ")
    if sub == "show" and rest:
        skill = registry.load(rest.strip())
        if not skill:
            console.print(f'Skill "{rest.strip()}" not found.')
            return
        console.print(skill.content[:12_000])
        return
    if sub == "on" and rest:
        console.print("enabled" if registry.enable(rest.strip()) else "skill not found")
        return
    if sub == "off" and rest:
        console.print("disabled" if registry.disable(rest.strip()) else "skill not found")
        return
    if sub == "reload":
        registry.reload()
        console.print("skills reloaded")
        return