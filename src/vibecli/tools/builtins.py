from __future__ import annotations

import asyncio
import glob as glob_module
import os
import re
from pathlib import Path
from typing import Any

from vibecli.lsp import diagnose_file
from vibecli.memory import MemoryManager
from vibecli.policy import CommandGuard, PathGuard
from vibecli.rag import CodeIndex
from vibecli.skill import SkillRegistry
from vibecli.snapshot import SnapshotService
from vibecli.tools.base import Tool, ToolContext, ToolResult, object_schema
from vibecli.web import fetch_url, search_web


def get_builtin_tools() -> list[Tool]:
    tools = [
        Tool(
            name="read_file",
            description="Read a text file from the current workspace.",
            parameters=object_schema(
                {
                    "path": {"type": "string", "description": "Path to read"},
                    "offset": {"type": "number", "description": "Start line, 1-based"},
                    "limit": {"type": "number", "description": "Maximum number of lines"},
                },
                ["path"],
            ),
            required_keys=["path"],
            handler=read_file,
        ),
        Tool(
            name="write_file",
            description="Write a UTF-8 text file inside the current workspace.",
            parameters=object_schema(
                {
                    "path": {"type": "string", "description": "Path to write"},
                    "content": {"type": "string", "description": "File content"},
                    "append": {"type": "boolean", "description": "Append instead of overwrite"},
                },
                ["path", "content"],
            ),
            required_keys=["path", "content"],
            handler=write_file,
            is_read_only=False,
            is_concurrency_safe=False,
            danger_level="medium",
        ),
        Tool(
            name="list_dir",
            description="List entries in a directory inside the current workspace.",
            parameters=object_schema(
                {"path": {"type": "string", "description": "Directory path"}},
                ["path"],
            ),
            required_keys=["path"],
            handler=list_dir,
        ),
        Tool(
            name="glob",
            description="Find files by glob pattern inside the current workspace.",
            parameters=object_schema(
                {
                    "pattern": {"type": "string", "description": "Glob pattern"},
                    "limit": {"type": "number", "description": "Maximum results"},
                },
                ["pattern"],
            ),
            required_keys=["pattern"],
            handler=glob_files,
        ),
        Tool(
            name="glob_files",
            description="Alias of glob. Find files by glob pattern inside the current workspace.",
            parameters=object_schema(
                {
                    "pattern": {"type": "string", "description": "Glob pattern"},
                    "limit": {"type": "number", "description": "Maximum results"},
                },
                ["pattern"],
            ),
            required_keys=["pattern"],
            handler=glob_files,
        ),
        Tool(
            name="grep",
            description="Search text in workspace files.",
            parameters=object_schema(
                {
                    "pattern": {"type": "string", "description": "Regex or plain text pattern"},
                    "path": {"type": "string", "description": "Optional path to search"},
                    "regex": {"type": "boolean", "description": "Treat pattern as regex"},
                    "limit": {"type": "number", "description": "Maximum matches"},
                },
                ["pattern"],
            ),
            required_keys=["pattern"],
            handler=grep,
        ),
        Tool(
            name="grep_code",
            description="Alias of grep. Search text in workspace files.",
            parameters=object_schema(
                {
                    "pattern": {"type": "string", "description": "Regex or plain text pattern"},
                    "path": {"type": "string", "description": "Optional path to search"},
                    "regex": {"type": "boolean", "description": "Treat pattern as regex"},
                    "limit": {"type": "number", "description": "Maximum matches"},
                },
                ["pattern"],
            ),
            required_keys=["pattern"],
            handler=grep,
        ),
        Tool(
            name="bash",
            description="Execute a shell command in the current workspace.",
            parameters=object_schema(
                {
                    "command": {"type": "string", "description": "Shell command"},
                    "timeout": {"type": "number", "description": "Timeout seconds"},
                },
                ["command"],
            ),
            required_keys=["command"],
            handler=bash,
            is_read_only=False,
            is_concurrency_safe=False,
            danger_level="high",
            requires_approval=True,
        ),
        Tool(
            name="execute_command",
            description="Alias of bash. Execute a shell command in the current workspace.",
            parameters=object_schema(
                {
                    "command": {"type": "string", "description": "Shell command"},
                    "timeout": {"type": "number", "description": "Timeout seconds"},
                },
                ["command"],
            ),
            required_keys=["command"],
            handler=bash,
            is_read_only=False,
            is_concurrency_safe=False,
            danger_level="high",
            requires_approval=True,
        ),
        Tool(
            name="web_search",
            description=(
                "Search the web for current information. Returns titles, URLs, and snippets."
            ),
            parameters=object_schema(
                {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "number", "description": "Maximum result count"},
                },
                ["query"],
            ),
            required_keys=["query"],
            handler=web_search,
        ),
        Tool(
            name="web_fetch",
            description="Fetch a public HTTP/HTTPS page and return readable text.",
            parameters=object_schema(
                {
                    "url": {"type": "string", "description": "URL to fetch"},
                    "max_length": {"type": "number", "description": "Maximum returned characters"},
                },
                ["url"],
            ),
            required_keys=["url"],
            handler=web_fetch,
        ),
        Tool(
            name="save_memory",
            description="Save a stable fact to long-term project memory.",
            parameters=object_schema(
                {"content": {"type": "string", "description": "Fact to remember"}},
                ["content"],
            ),
            required_keys=["content"],
            handler=save_memory,
            is_read_only=False,
            is_concurrency_safe=False,
            danger_level="medium",
        ),
        Tool(
            name="load_skill",
            description="Load a named VibeCLI skill manual from user/project skill directories.",
            parameters=object_schema(
                {"name": {"type": "string", "description": "Skill name"}},
                ["name"],
            ),
            required_keys=["name"],
            handler=load_skill,
        ),
        Tool(
            name="search_code",
            description="Search the local code index for semantically relevant lines.",
            parameters=object_schema(
                {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "number", "description": "Maximum matches"},
                },
                ["query"],
            ),
            required_keys=["query"],
            handler=search_code,
        ),
        Tool(
            name="revert_turn",
            description="Restore the workspace to a previous VibeCLI side-history snapshot.",
            parameters=object_schema(
                {"snapshot": {"type": "string", "description": "Snapshot id or 1-based index"}},
                ["snapshot"],
            ),
            required_keys=["snapshot"],
            handler=revert_turn,
            is_read_only=False,
            is_concurrency_safe=False,
            danger_level="high",
            requires_approval=True,
        ),
    ]
    return tools


async def read_file(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    path = _resolve_path(context, str(payload["path"]))
    offset = max(int(payload.get("offset") or 1), 1)
    limit = int(payload.get("limit") or 500)
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    selected = content[offset - 1 : offset - 1 + limit]
    numbered = "\n".join(f"{idx + offset}: {line}" for idx, line in enumerate(selected))
    return ToolResult(numbered, display_summary=f"Read {path.relative_to(context.cwd)}")


async def write_file(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    path = _resolve_path(context, str(payload["path"]))
    content = str(payload["content"])
    if len(content.encode("utf-8")) > 5 * 1024 * 1024:
        return ToolResult("write_file rejected: content exceeds 5MB", is_error=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if payload.get("append") else "w"
    with path.open(mode, encoding="utf-8") as handle:
        handle.write(content)
    rel = path.relative_to(context.cwd)
    diagnostics = diagnose_file(path)
    suffix = ""
    if diagnostics:
        suffix = "\n\nDiagnostics:\n" + "\n".join(diagnostics)
    return ToolResult(f"Wrote {rel}{suffix}", display_summary=f"Wrote {rel}")


async def list_dir(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    path = _resolve_path(context, str(payload["path"]))
    if not path.is_dir():
        return ToolResult(f"Not a directory: {path}", is_error=True)
    rows = []
    for child in sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        marker = "/" if child.is_dir() else ""
        rows.append(f"{child.name}{marker}")
    return ToolResult("\n".join(rows) or "(empty directory)")


async def glob_files(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    root = Path(context.cwd).resolve()
    pattern = str(payload["pattern"])
    if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
        return ToolResult("glob pattern must stay inside workspace", is_error=True)
    limit = int(payload.get("limit") or 100)
    matches = glob_module.glob(str(root / pattern), recursive=True)
    rels = []
    for match in sorted(matches):
        path = Path(match).resolve()
        try:
            rels.append(str(path.relative_to(root)))
        except ValueError:
            continue
        if len(rels) >= limit:
            break
    return ToolResult("\n".join(rels) or "(no matches)")


async def grep(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    root = Path(context.cwd).resolve()
    start = _resolve_path(context, str(payload.get("path") or "."))
    pattern = str(payload["pattern"])
    limit = int(payload.get("limit") or 100)
    use_regex = bool(payload.get("regex", True))
    try:
        compiled = re.compile(pattern) if use_regex else None
    except re.error as exc:
        return ToolResult(f"invalid regex: {exc}", is_error=True)

    matches: list[str] = []
    files = [start] if start.is_file() else [p for p in start.rglob("*") if p.is_file()]
    for file_path in files:
        if _skip_file(file_path):
            continue
        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            found = bool(compiled.search(line)) if compiled else pattern in line
            if found:
                matches.append(f"{file_path.relative_to(root)}:{line_number}: {line.strip()}")
                if len(matches) >= limit:
                    return ToolResult("\n".join(matches))
    return ToolResult("\n".join(matches) or "(no matches)")


async def bash(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    command = str(payload["command"])
    CommandGuard(context.config.policy.command_blacklist).validate(command)
    timeout = float(payload.get("timeout") or context.config.tools.timeout)
    proc = await asyncio.create_subprocess_shell(
        command,
        cwd=context.cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=os.environ.copy(),
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return ToolResult(f"Command timed out after {timeout:.0f}s", is_error=True)
    output = (stdout + stderr).decode("utf-8", errors="replace")
    if len(output) > 20_000:
        output = output[:20_000] + "\n... [truncated]"
    return ToolResult(
        output or f"(exit {proc.returncode}, no output)",
        is_error=proc.returncode != 0,
    )


async def web_search(payload: dict[str, Any], _context: ToolContext) -> ToolResult:
    max_results = int(payload.get("max_results") or payload.get("maxResults") or 5)
    try:
        results = await search_web(str(payload["query"]), max_results=max_results)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(f"Search error: {exc}", is_error=True)