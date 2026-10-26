from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from vibecli.config import VibeCliConfig
from vibecli.tools import ToolRegistry, get_builtin_tools
from vibecli.tools.base import ToolContext
from vibecli.tools.executor import ToolExecutor

EXPECTED_TOOLS = {
    "read_file",
    "write_file",
    "list_dir",
    "glob",
    "glob_files",
    "grep",
    "grep_code",
    "bash",
    "execute_command",
    "web_search",
    "web_fetch",
    "save_memory",
    "load_skill",
    "search_code",
    "revert_turn",
}


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register_all(get_builtin_tools())
    return registry


def make_context(workspace: Path, *, hitl_mode: str = "never", approval=None) -> ToolContext:
    config = VibeCliConfig()
    config.llm.api_key = "test-key"
    config.policy.hitl_mode = hitl_mode
    config.policy.audit_log_path = str(workspace / "audit.jsonl")
    return ToolContext(cwd=str(workspace), config=config, approval_callback=approval)


def test_builtin_tool_set_is_exact() -> None:
    assert set(build_registry().list_names()) == EXPECTED_TOOLS


def test_tool_definitions_are_openai_shaped() -> None:
    definitions = build_registry().definitions()

    assert len(definitions) == len(EXPECTED_TOOLS)
    for definition in definitions:
        assert definition["type"] == "function"
        function = definition["function"]
        assert function["name"]
        assert function["description"]
        assert function["parameters"]["type"] == "object"


def test_dangerous_tools_require_approval() -> None:
    registry = build_registry()

    for name in ("bash", "execute_command", "revert_turn"):
        tool = registry.get(name)
        assert tool is not None
        assert tool.requires_approval is True
        assert tool.danger_level == "high"


def test_read_only_tools_are_concurrency_safe() -> None:
    registry = build_registry()

    for name in ("read_file", "list_dir", "glob", "grep", "search_code"):
        tool = registry.get(name)
        assert tool is not None
        assert tool.is_read_only is True
        assert tool.is_concurrency_safe is True


def test_read_file_returns_numbered_lines(workspace: Path) -> None:
    (workspace / "notes.txt").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    executor = ToolExecutor(build_registry())

    results = asyncio.run(
        executor.execute_all(
            [
                {
                    "id": "call_1",
                    "function": {"name": "read_file", "arguments": '{"path": "notes.txt"}'},
                }
            ],
            make_context(workspace),
        )
    )

    assert len(results) == 1
    assert results[0].is_error is False
    assert results[0].tool_use_id == "call_1"
    assert "1: alpha" in results[0].content
    assert "3: gamma" in results[0].content


def test_write_file_stays_inside_workspace(workspace: Path) -> None:
    executor = ToolExecutor(build_registry())

    results = asyncio.run(
        executor.execute_all(
            [
                {
                    "id": "call_1",
                    "function": {
                        "name": "write_file",
                        "arguments": '{"path": "nested/out.txt", "content": "hello"}',
                    },
                }
            ],
            make_context(workspace),
        )
    )

    assert results[0].is_error is False
    assert (workspace / "nested" / "out.txt").read_text(encoding="utf-8") == "hello"


def test_write_file_outside_workspace_is_rejected(workspace: Path) -> None:
    executor = ToolExecutor(build_registry())

    results = asyncio.run(
        executor.execute_all(
            [
                {
                    "id": "call_1",
                    "function": {
                        "name": "write_file",
                        "arguments": '{"path": "../escape.txt", "content": "nope"}',
                    },
                }
            ],
            make_context(workspace),
        )
    )

    assert results[0].is_error is True
    assert "escapes workspace" in results[0].content
    assert not (workspace.parent / "escape.txt").exists()


def test_destructive_command_is_blocked(workspace: Path) -> None:
    executor = ToolExecutor(build_registry())

    results = asyncio.run(
        executor.execute_all(
            [
                {
                    "id": "call_1",
                    "function": {"name": "bash", "arguments": '{"command": "rm -rf /"}'},
                }
            ],
            make_context(workspace, hitl_mode="never"),
        )
    )

    assert results[0].is_error is True
    assert "policy" in results[0].content.lower()


def test_hitl_denial_short_circuits_execution(workspace: Path) -> None:
    executor = ToolExecutor(build_registry())
    seen: list[dict] = []

    def deny(request: dict) -> str:
        seen.append(request)
        return "deny"

    results = asyncio.run(
        executor.execute_all(
            [
                {
                    "id": "call_1",
                    "function": {"name": "bash", "arguments": '{"command": "echo hi"}'},
                }
            ],
            make_context(workspace, hitl_mode="always", approval=deny),
        )
    )

    assert seen and seen[0]["tool_name"] == "bash"
    assert seen[0]["danger_level"] == "high"
    assert results[0].is_error is True
    assert "denied" in results[0].content
    assert (workspace / "audit.jsonl").read_text(encoding="utf-8").count("deny") >= 1


def test_missing_required_argument_surfaces_as_tool_error(workspace: Path) -> None:
    executor = ToolExecutor(build_registry())

    results = asyncio.run(
        executor.execute_all(
            [{"id": "call_1", "function": {"name": "read_file", "arguments": "{}"}}],
            make_context(workspace),
        )
    )

    assert results[0].is_error is True
    assert "missing required input" in results[0].content


def test_unknown_tool_reports_available_tools(workspace: Path) -> None:
    executor = ToolExecutor(build_registry())

    results = asyncio.run(
        executor.execute_all(
            [{"id": "call_1", "function": {"name": "no_such_tool", "arguments": "{}"}}],
            make_context(workspace),
        )
    )

    assert results[0].is_error is True
    assert "not found" in results[0].content
    assert "read_file" in results[0].content


def test_read_only_tools_run_concurrently(workspace: Path) -> None:
    for index in range(4):
        (workspace / f"file_{index}.txt").write_text(f"content {index}", encoding="utf-8")
    executor = ToolExecutor(build_registry())

    calls = [
        {
            "id": f"call_{index}",
            "function": {"name": "read_file", "arguments": f'{{"path": "file_{index}.txt"}}'},
        }
        for index in range(4)
    ]
    results = asyncio.run(executor.execute_all(calls, make_context(workspace)))

    assert [result.tool_use_id for result in results] == [f"call_{i}" for i in range(4)]
    assert all(not result.is_error for result in results)


def test_sequential_tools_keep_declaration_order(workspace: Path) -> None:
    executor = ToolExecutor(build_registry())

    results = asyncio.run(
        executor.execute_all(
            [
                {
                    "id": "call_1",
                    "function": {
                        "name": "write_file",
                        "arguments": '{"path": "a.txt", "content": "1"}',
                    },
                },
                {
                    "id": "call_2",
                    "function": {
                        "name": "write_file",
                        "arguments": '{"path": "b.txt", "content": "2"}',
                    },
                },
            ],
            make_context(workspace),
        )
    )

    assert [result.tool_use_id for result in results] == ["call_1", "call_2"]
    assert (workspace / "a.txt").read_text(encoding="utf-8") == "1"
    assert (workspace / "b.txt").read_text(encoding="utf-8") == "2"


@pytest.mark.parametrize(
    "arguments",
    ['{"path": "a.txt"}', "not-json"],
)
def test_arguments_parsing_never_raises(workspace: Path, arguments: str) -> None:
    executor = ToolExecutor(build_registry())

    results = asyncio.run(
        executor.execute_all(
            [{"id": "call_1", "function": {"name": "list_dir", "arguments": arguments}}],
            make_context(workspace),
        )
    )

    assert len(results) == 1
