from __future__ import annotations

import io
import sys
from unittest.mock import MagicMock, patch

from rich.console import Console

from vibecli.config import VibeCliConfig
from vibecli.entrypoints.repl import _approval_prompt
from vibecli.tools.builtins import _decode_output, _resolve_posix_shell


def test_decode_output_handles_gbk_console_bytes() -> None:
    """Windows cmd writes GBK; decoding as UTF-8 used to yield mojibake."""
    raw = "文件名不存在".encode("gbk")
    assert _decode_output(raw) == "文件名不存在"


def test_decode_output_prefers_utf8() -> None:
    raw = "中文测试".encode()
    assert _decode_output(raw) == "中文测试"


def test_decode_output_empty() -> None:
    assert _decode_output(b"") == ""


def test_resolve_posix_shell_disabled_by_override(monkeypatch) -> None:
    monkeypatch.setenv("VIBECLI_SHELL", "cmd")
    assert _resolve_posix_shell() is None


def test_approval_prompt_keeps_bracket_payload() -> None:
    """Rich markup used to swallow ``[pathlib.Path('src')]`` from the command."""
    buffer = io.StringIO()
    console = Console(file=buffer, width=200, no_color=True, highlight=False)
    request = {
        "tool_name": "bash",
        "danger_level": "high",
        "input": {"command": "for p in [pathlib.Path('src')]: print(p)"},
    }
    fake_stdin = MagicMock()
    fake_stdin.isatty.return_value = True
    with (
        patch.object(sys, "stdin", fake_stdin),
        patch("vibecli.entrypoints.repl.Prompt.ask", return_value="n"),
    ):
        assert _approval_prompt(request, console, VibeCliConfig()) == "deny"
    assert "[pathlib.Path('src')]" in buffer.getvalue()
