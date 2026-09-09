from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import threading
import time
from dataclasses import asdict
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from vibecli.agent import QueryEngine
from vibecli.bootstrap import build_tool_registry
from vibecli.config import VibeCliConfig
from vibecli.llm import create_llm_client
from vibecli.runtime.tasks import DurableTaskManager


class RuntimeApiServer:
    def __init__(
        self,
        *,
        cwd: str,
        config: VibeCliConfig,
        api_key: str,
        port: int = 8080,
        workers: int = 2,
    ):
        self.cwd = str(Path(cwd).resolve())
        self.config = config
        self.api_key = api_key
        self.port = port
        self.db_path = Path.home() / ".vibecli" / "runtime" / "runtime.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.task_manager = DurableTaskManager(Path.home() / ".vibecli" / "tasks" / "tasks.db")
        self.workers = workers
        self._stop = threading.Event()
        self._ensure_schema()

    def serve_forever(self) -> None:
        for index in range(self.workers):
            thread = threading.Thread(
                target=self._worker_loop,
                name=f"vibecli-task-{index}",
                daemon=True,
            )
            thread.start()

        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                outer._handle(self)

            def do_GET(self) -> None:  # noqa: N802
                outer._handle(self)

            def log_message(self, _format: str, *args: Any) -> None:
                return

        server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        print(f"VibeCLI Runtime API listening on http://127.0.0.1:{self.port}", flush=True)
        try:
            server.serve_forever()
        finally:
            self._stop.set()
