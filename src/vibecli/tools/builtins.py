from __future__ import annotations

import asyncio
import glob as glob_module
import os
import re
import shutil
from pathlib import Path
from typing import Any

from vibecli.lsp import diagnose_file
from vibecli.memory import MemoryManager
from vibecli.policy import CommandGuard, PathGuard
from vibecli.rag import CodeIndex
from vibecli.skill import SkillRegistry
from vibecli.snapshot import SnapshotService
from vibecli.textio import decode_bytes, is_utf8, read_text_file
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
            description=(
                "Execute a shell command in the current workspace. Runs through a POSIX "
                "shell (bash/sh) when one is available, otherwise the platform default. "
                "Prefer portable commands and quote paths containing spaces."
            ),
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
            description=(
                "Alias of bash. Execute a shell command in the current workspace through "
                "a POSIX shell (bash/sh) when one is available."
            ),
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
    text, encoding = read_text_file(path)
    content = text.splitlines()
    selected = content[offset - 1 : offset - 1 + limit]
    numbered = "\n".join(f"{idx + offset}: {line}" for idx, line in enumerate(selected))
    header = ""
    if not is_utf8(encoding):
        # 明确告诉模型这份内容的编码。否则它会把非 UTF-8 的字节当成正常文本
        # 编辑，写回时把整份文件的中文毁掉。
        header = (
            f"[note] {path.relative_to(context.cwd)} is encoded as {encoding}, not UTF-8. "
            "write_file keeps this encoding when it can.\n"
        )
    return ToolResult(header + numbered, display_summary=f"Read {path.relative_to(context.cwd)}")


async def write_file(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    path = _resolve_path(context, str(payload["path"]))
    content = str(payload["content"])
    if len(content.encode("utf-8")) > 5 * 1024 * 1024:
        return ToolResult("write_file rejected: content exceeds 5MB", is_error=True)

    # 读什么编码就写什么编码。一律转 UTF-8 会让遗留 GBK 项目的注释内容和
    # coding 声明互相矛盾，转完直接语法错误。
    original = read_text_file(path)[1] if path.is_file() else None
    encoding = "utf-8" if original is None or is_utf8(original) else original
    try:
        data = content.encode(encoding)
    except UnicodeEncodeError:
        # 内容里有原编码表示不了的字符（emoji、生僻字）：退回 UTF-8，并同步
        # 改掉头部声明，避免「字节是 UTF-8、声明说 GBK」的自相矛盾。
        encoding = "utf-8"
        content = _retarget_coding_declaration(content, "utf-8")
        data = content.encode("utf-8")

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab" if payload.get("append") else "wb") as handle:
        handle.write(data)

    rel = path.relative_to(context.cwd)
    suffix = ""
    if original is not None and not is_utf8(original):
        if is_utf8(encoding):
            suffix += f"\n[note] {rel} was {original}; rewritten as UTF-8 (fallback)."
        else:
            suffix += f"\n[note] {rel} kept {encoding} encoding."
    diagnostics = diagnose_file(path)
    if diagnostics:
        suffix += "\n\nDiagnostics:\n" + "\n".join(diagnostics)
    return ToolResult(f"Wrote {rel}{suffix}", display_summary=f"Wrote {rel}")


_CODING_DECLARATION = re.compile(r"coding[:=]\s*([-\w.]+)")


def _retarget_coding_declaration(text: str, encoding: str) -> str:
    """改写源文件头部的编码声明。

    转码后若继续保留 ``# -*- coding: gbk -*-``，Python 会拿 GBK 去解一份
    UTF-8 字节，直接 SyntaxError —— 转码反而把文件弄成语法错误。
    """
    head, separator, rest = text.partition("\n")
    if not _CODING_DECLARATION.search(head):
        return text
    return _CODING_DECLARATION.sub(f"coding: {encoding}", head, count=1) + separator + rest


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
            lines = read_text_file(file_path)[0].splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            found = bool(compiled.search(line)) if compiled else pattern in line
            if found:
                matches.append(f"{file_path.relative_to(root)}:{line_number}: {line.strip()}")
                if len(matches) >= limit:
                    return ToolResult("\n".join(matches))
    return ToolResult("\n".join(matches) or "(no matches)")


_SHELL_DISABLED_VALUES = {"", "default", "cmd", "cmd.exe", "powershell", "pwsh"}


def _resolve_posix_shell() -> str | None:
    """Windows 上优先用 POSIX shell，让 find/head/wc/grep 这些命令能用。

    - 非 Windows：返回 None，保持 /bin/sh 的默认行为
    - `VIBECLI_SHELL=bash 路径`：显式指定
    - `VIBECLI_SHELL=cmd|default|powershell`：强制回退系统 shell
    """
    override = os.environ.get("VIBECLI_SHELL", "").strip()
    if override:
        if override.lower() in _SHELL_DISABLED_VALUES:
            return None
        if Path(override).exists() or shutil.which(override):
            return override
        return None
    if os.name != "nt":
        return None
    return shutil.which("bash")


def _decode_output(raw: bytes) -> str:
    """解码子进程输出，逐行判断编码（同一流里可能混着 UTF-8 和 GBK）。"""
    return decode_bytes(raw)[0]


async def bash(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    command = str(payload["command"])
    CommandGuard(context.config.policy.command_blacklist).validate(command)
    timeout = float(payload.get("timeout") or context.config.tools.timeout)
    shell = _resolve_posix_shell()
    spawn = asyncio.create_subprocess_exec if shell else asyncio.create_subprocess_shell
    args = [shell, "-c", command] if shell else [command]
    proc = await spawn(
        *args,
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
    output = _decode_output(stdout + stderr)
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
    if not results:
        return ToolResult(f'No search results found for "{payload["query"]}".')
    content = "\n\n".join(
        f"{index}. {result.title}\n{result.url}\n{result.snippet}"
        for index, result in enumerate(results, start=1)
    )
    return ToolResult(content, display_summary=f"Search: {len(results)} results")


async def web_fetch(payload: dict[str, Any], _context: ToolContext) -> ToolResult:
    max_length = int(payload.get("max_length") or payload.get("maxLength") or 10_000)
    try:
        content = await fetch_url(str(payload["url"]), max_length=max_length)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(f"Fetch error: {exc}", is_error=True)
    return ToolResult(content, display_summary=f"Fetched {payload['url']}")


async def save_memory(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    if not context.config.features.memory or not context.config.memory.long_term_enabled:
        return ToolResult("Long-term memory is disabled.", is_error=True)
    manager = MemoryManager(context.config.memory.long_term_db_path, scope=context.cwd)
    memory_id = manager.save(str(payload["content"]))
    return ToolResult(f"Saved memory #{memory_id}")


async def load_skill(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    skill = SkillRegistry(context.cwd).load(str(payload["name"]))
    if not skill:
        return ToolResult(f'Skill "{payload["name"]}" not found or disabled.', is_error=True)
    content = skill.body or skill.content
    if len(content) > 5_000:
        content = content[:5_000] + "\n... [truncated; use /skill show for the full skill]"
    if context.skill_context_buffer:
        context.skill_context_buffer.push(skill.name, content)
        return ToolResult(
            f'Loaded skill "{skill.name}" instructions for the next model turn.',
            display_summary=f"Loaded skill {skill.name}",
        )
    return ToolResult(content, display_summary=f"Loaded skill {skill.name}")


async def search_code(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    index = CodeIndex(context.cwd)
    results = index.search(str(payload["query"]), limit=int(payload.get("limit") or 20))
    if not results:
        return ToolResult("(no indexed matches; run /index first)")
    return ToolResult("\n".join(f"{item.path}:{item.line}: {item.snippet}" for item in results))


async def revert_turn(payload: dict[str, Any], context: ToolContext) -> ToolResult:
    record = SnapshotService(context.cwd).restore(str(payload["snapshot"]))
    return ToolResult(f"Restored snapshot {record.id}")


def _resolve_path(context: ToolContext, value: str) -> Path:
    if context.config.policy.path_guard_enabled:
        return PathGuard(context.cwd).validate(value)
    path = Path(value)
    return path if path.is_absolute() else Path(context.cwd).resolve() / path


def _skip_file(path: Path) -> bool:
    skip_dirs = {".git", ".venv", "node_modules", "dist", "build", "target"}
    if any(part in skip_dirs for part in path.parts):
        return True
    return path.stat().st_size > 1_000_000
