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

    def _handle(self, request: BaseHTTPRequestHandler) -> None:
        if not self._authorized(request):
            _send_json(request, 401, {"error": "unauthorized"})
            return
        method = request.command
        path = request.path.split("?", 1)[0]
        body = _read_json(request)
        try:
            if method == "POST" and path == "/v1/threads":
                thread_id = self._create_thread()
                _send_json(request, 200, {"id": thread_id})
            elif method == "POST" and path.startswith("/v1/threads/") and path.endswith("/turns"):
                thread_id = path.split("/")[3]
                message = str(body.get("message") or body.get("prompt") or "")
                if not message:
                    _send_json(request, 400, {"error": "message is required"})
                    return
                result = asyncio.run(self._run_turn(thread_id, message))
                _send_json(request, 200, result)
            elif method == "GET" and path.startswith("/v1/threads/") and path.endswith("/events"):
                thread_id = path.split("/")[3]
                self._send_events(request, thread_id)
            elif method == "POST" and path == "/v1/tasks":
                prompt = str(body.get("message") or body.get("prompt") or "")
                if not prompt:
                    _send_json(request, 400, {"error": "message is required"})
                    return
                task_id = self.task_manager.add(prompt)
                _send_json(request, 200, {"id": task_id, "status": "queued"})
            elif method == "GET" and path == "/v1/tasks":
                _send_json(request, 200, {"tasks": [asdict(t) for t in self.task_manager.list()]})
            elif method == "GET" and path.startswith("/v1/tasks/"):
                task = self.task_manager.get(path.split("/")[3])
                payload = asdict(task) if task else {"error": "not found"}
                _send_json(request, 200 if task else 404, payload)
            elif method == "POST" and path.startswith("/v1/tasks/") and path.endswith("/cancel"):
                task_id = path.split("/")[3]
                _send_json(request, 200, {"canceled": self.task_manager.cancel(task_id)})
            else:
                _send_json(request, 404, {"error": "not found"})
        except Exception as exc:  # noqa: BLE001 - API boundary
            _send_json(request, 500, {"error": str(exc)})