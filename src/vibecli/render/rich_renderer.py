from __future__ import annotations

import json
from typing import Any

from rich import box
from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class RichRenderer:
    def __init__(
        self,
        console: Console | None = None,
        *,
        live_markdown: bool = False,
        context_window: int | None = None,
    ):
        self.console = console or Console()
        self._buffer: list[str] = []
        self._thinking_buffer: list[str] = []
        self._live_markdown = live_markdown
        self._live: Live | None = None
        self._thinking_live: Live | None = None
        self._context_window = context_window or 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._last_input_tokens = 0
        self._last_turns = 0
        self._last_total_tokens = 0
        self._last_context_ratio = 0.0
        self._last_has_usage = False

    def set_context_window(self, context_window: int | None) -> None:
        self._context_window = context_window or self._context_window

    def start_run(self) -> None:
        self._buffer.clear()
        self._thinking_buffer.clear()
        self._stop_live_markdown()
        self._stop_live_thinking()
        self._input_tokens = 0
        self._output_tokens = 0
        self._last_input_tokens = 0

    def toolbar_status(self) -> dict[str, Any]:
        return {
            "turns": self._last_turns,
            "input_tokens": self._input_tokens,
            "output_tokens": self._output_tokens,
            "total_tokens": self._last_total_tokens,
            "context_ratio": self._last_context_ratio,
            "has_usage": self._last_has_usage,
        }

    def banner(
        self,
        *,
        model: str,
        provider: str,
        cwd: str,
        tools: int,
        version: str = "0.1.0",
        api_key_configured: bool = False,
        mcp_servers: int = 0,
        skills: int = 0,
        agents_files: int = 0,
        hitl_mode: str = "auto",
    ) -> None:
        top = Table.grid(expand=True)
        top.add_column(ratio=1)
        top.add_column(ratio=2)
        top.add_row(
            self._identity_panel(version=version, api_key_configured=api_key_configured),
            self._release_panel(version=version),
        )

        _ = model, provider, cwd, tools, mcp_servers, skills, agents_files, hitl_mode

        self.console.print()
        self.console.print(top)
        self.console.print(Align.right(Text("? for shortcuts", style="dim")))
        self.console.rule(style="grey23")
        self.console.print()

    def handle(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type == "text_delta":
            self._flush_thinking()
            text = str(event.get("text") or "")
            self._buffer.append(text)
            self._update_live_markdown()
        elif event_type == "thinking_delta":
            thinking = str(event.get("thinking") or "")
            self._thinking_buffer.append(thinking)
            self._update_live_thinking()
        elif event_type == "usage":
            self._record_usage(event.get("usage") or {})
        elif event_type == "turn_complete":
            stop_reason = str(event.get("stop_reason") or "end_turn")
            title = "Assistant Output" if stop_reason == "tool_use" else "Final Output"
            self._flush_thinking()
            self._flush_markdown(title=title)
        elif event_type == "tool_call":
            self._flush_thinking()
            self._flush_markdown(title="Assistant Output")
            self._print_tool_call(event)
        elif event_type == "tool_result":
            self._flush_thinking()
            self._flush_markdown(title="Assistant Output")
            self._print_tool_result(event)
        elif event_type == "error":
            self._flush_thinking()
            self._flush_markdown(title="Assistant Output")
            self.console.print(f"[red]Error:[/red] {event.get('error')}")
        elif event_type == "done":
            self._flush_thinking()
            self._flush_markdown(title="Final Output")
            self._record_run_summary(event)
