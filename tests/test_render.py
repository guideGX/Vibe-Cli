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