from __future__ import annotations

from io import StringIO

from rich.console import Console

from vibecli.entrypoints.repl import _bottom_toolbar, _prompt_message
from vibecli.render import RichRenderer


def test_banner_renders_pi_home_layout():
    stream = StringIO()
    console = Console(file=stream, color_system=None, width=200)
    renderer = RichRenderer(console=console)

    renderer.banner(
        model="deepseek-v4-flash",
        provider="deepseek",
        cwd="/tmp/project",
        tools=12,
        version="0.1.0",
        api_key_configured=True,
        mcp_servers=1,
        skills=3,
        agents_files=2,
        hitl_mode="never",
    )

    output = stream.getvalue()
    assert "████████████" in output
    assert "  ██    ██" in output
    assert "VibeCLI v0.1.0" in output
    assert "Signed in API Key" in output
    assert "What's new (v0.1.0)" in output


def test_prompt_message_keeps_status_and_input_together():
    prompt = _prompt_message(
        cwd="/tmp/project",
        model="deepseek-v4-flash",
        tools=12,
        agents_files=2,
        mcp_servers=1,
        skills=3,
        stats={"total_tokens": 13187, "context_ratio": 0.013, "has_usage": True},
    )
    plain = "".join(text for _style, text in prompt)

    assert "2 AGENTS.md files" in plain
    assert "1 MCP server" in plain
    assert "3 skills · Tools 12" in plain
    assert "YOLO" not in plain
    assert "Shift+Tab" not in plain
    assert "deepseek-v4-flash" in plain
    assert "█░░░░░░░░░░░ 1%" in plain
    assert "/tmp/project" in plain
    assert "\n\n* " in plain
    assert plain.endswith("\n* ")


def test_bottom_toolbar_uses_runtime_summary_segments():
    toolbar = _bottom_toolbar(
        "/Users/me/project",
        "deepseek-v4-flash",
        {"turns": 1, "total_tokens": 13187, "context_ratio": 0.013, "has_usage": True},
    )

    assert ("class:toolbar.model", "deepseek-v4-flash") in toolbar
    assert ("class:toolbar.ctx.bar", "█░░░░░░░░░░░") in toolbar
    assert ("class:toolbar.ctx.value", "1%") in toolbar
    assert ("class:toolbar.cwd.value", "/Users/me/project") in toolbar
    assert not any(text == " TURN " for _style, text in toolbar)
    assert not any("Token" in text for _style, text in toolbar)


def test_text_deltas_render_as_markdown_on_turn_complete():
    stream = StringIO()
    console = Console(file=stream, color_system=None, width=120)
    renderer = RichRenderer(console=console, context_window=1000)

    renderer.handle({"type": "thinking_delta", "thinking": "需要先确认项目结构"})
    renderer.handle({"type": "text_delta", "text": "你好，我是 **Vibe"})
    renderer.handle({"type": "text_delta", "text": "CLI**\n\n- `read_file`\n- **网页搜索**"})
    renderer.handle({"type": "usage", "usage": {"input_tokens": 250, "output_tokens": 50}})
    renderer.handle({"type": "turn_complete"})
    renderer.handle({"type": "done", "total_turns": 1, "total_tokens": 300})

    output = stream.getvalue()
    assert "Thinking" in output
    assert "需要先确认项目结构" in output
    assert "Final Output" in output
    assert "VibeCLI" in output
    assert "read_file" in output
    assert "网页搜索" in output
    assert "Run Summary" not in output
    assert "**VibeCLI**" not in output
    assert "`read_file`" not in output

    stats = renderer.toolbar_status()
    assert stats["turns"] == 1
    assert stats["input_tokens"] == 250