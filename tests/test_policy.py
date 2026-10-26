from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecli.config import VibeCliConfig
from vibecli.policy import AuditLog, CommandGuard, PathGuard
from vibecli.policy.command_guard import CommandPolicyError
from vibecli.policy.path_guard import PathPolicyError

BLACKLIST = VibeCliConfig().policy.command_blacklist


def test_path_guard_allows_paths_inside_workspace(workspace: Path) -> None:
    guard = PathGuard(workspace)

    assert guard.validate("src/app.py") == (workspace / "src" / "app.py").resolve()
    assert guard.validate(workspace) == workspace.resolve()


def test_path_guard_rejects_escape_attempts(workspace: Path) -> None:
    guard = PathGuard(workspace)

    with pytest.raises(PathPolicyError):
        guard.validate("../outside.txt")
    with pytest.raises(PathPolicyError):
        guard.validate("/etc/passwd")


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /",
        "rm -rf ~",
        "sudo apt install sl",
        "mkfs.ext4 /dev/sda1",
        "dd if=/dev/zero of=/dev/sda",
        ":(){:|:&};:",
        "chmod -R 777 /",
        "shutdown -h now",
        "reboot",
        "find / -name id_rsa",
    ],
)
def test_command_guard_blocks_destructive_commands(command: str) -> None:
    guard = CommandGuard(blacklist=BLACKLIST)

    with pytest.raises(CommandPolicyError):
        guard.validate(command)


@pytest.mark.parametrize(
    "command",
    [
        "ls -la",
        "uv run pytest",
        "git status",
        "python -m pytest tests/test_config.py",
        "rm ./build.log",
    ],
)
def test_command_guard_allows_ordinary_commands(command: str) -> None:
    guard = CommandGuard(blacklist=BLACKLIST)

    guard.validate(command)


def test_command_guard_normalizes_whitespace() -> None:
    guard = CommandGuard(blacklist=BLACKLIST)

    with pytest.raises(CommandPolicyError):
        guard.validate("rm    -rf    /")


def test_audit_log_records_and_redacts(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)

    log.record(
        tool_name="bash",
        input_data={"command": "ls", "api_key": "sk-should-not-leak", "nested": {"token": "abc"}},
        outcome="allow",
        approver="hitl",
        cwd=str(tmp_path),
    )

    events = log.tail(5)
    assert len(events) == 1
    assert events[0]["tool_name"] == "bash"
    assert events[0]["input"]["api_key"] == "***"
    assert events[0]["input"]["nested"]["token"] == "***"
    assert "sk-should-not-leak" not in path.read_text(encoding="utf-8")


def test_audit_log_tail_is_limited_and_ordered(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "audit.jsonl")
    for index in range(5):
        log.record(
            tool_name=f"tool_{index}",
            input_data={},
            outcome="allow",
            approver="none",
            cwd=str(tmp_path),
        )

    events = log.tail(2)

    assert [event["tool_name"] for event in events] == ["tool_3", "tool_4"]


def test_audit_log_ignores_corrupted_lines(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text(
        json.dumps({"tool_name": "ok", "input": {}, "outcome": "allow"}) + "\n{not json}\n",
        encoding="utf-8",
    )

    assert [event["tool_name"] for event in AuditLog(path).tail(10)] == ["ok"]
