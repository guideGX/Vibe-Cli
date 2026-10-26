from __future__ import annotations

import json
import socket
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from vibecli.config import VibeCliConfig
from vibecli.runtime import RuntimeApiServer

API_KEY = "test-runtime-key"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def running_server(workspace: Path) -> Iterator[str]:
    config = VibeCliConfig()
    config.llm.api_key = ""
    port = free_port()
    server = RuntimeApiServer(
        cwd=str(workspace), config=config, api_key=API_KEY, port=port, workers=0
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            continue
    try:
        yield base
    finally:
        server._stop.set()


def call(
    base: str,
    path: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    api_key: str | None = API_KEY,
) -> tuple[int, str]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(f"{base}{path}", data=data, method=method)
    if data:
        request.add_header("content-type", "application/json")
    if api_key:
        request.add_header("x-api-key", api_key)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8")


def test_requests_without_key_are_rejected(fake_home: Path, workspace: Path) -> None:
    with running_server(workspace) as base:
        status, body = call(base, "/v1/threads", method="POST", api_key=None)

    assert status == 401
    assert json.loads(body)["error"] == "unauthorized"


def test_bearer_token_is_accepted(fake_home: Path, workspace: Path) -> None:
    with running_server(workspace) as base:
        request = urllib.request.Request(f"{base}/v1/threads", data=b"", method="POST")
        request.add_header("authorization", f"Bearer {API_KEY}")
        with urllib.request.urlopen(request, timeout=10) as response:
            assert response.status == 200
            assert json.loads(response.read())["id"].startswith("thread_")


def test_thread_creation_and_event_log(fake_home: Path, workspace: Path) -> None:
    with running_server(workspace) as base:
        status, body = call(base, "/v1/threads", method="POST")
        assert status == 200
        thread_id = json.loads(body)["id"]

        status, events = call(base, f"/v1/threads/{thread_id}/events")

    assert status == 200
    assert "event: thread.created" in events
    assert thread_id in events


def test_turn_without_llm_key_returns_server_error(fake_home: Path, workspace: Path) -> None:
    with running_server(workspace) as base:
        _, body = call(base, "/v1/threads", method="POST")
        thread_id = json.loads(body)["id"]

        status, payload = call(
            base,
            f"/v1/threads/{thread_id}/turns",
            method="POST",
            body={"message": "hello"},
        )

    assert status == 500
    assert "VIBECLI_API_KEY" in json.loads(payload)["error"]


def test_turn_requires_a_message(fake_home: Path, workspace: Path) -> None:
    with running_server(workspace) as base:
        _, body = call(base, "/v1/threads", method="POST")
        thread_id = json.loads(body)["id"]

        status, payload = call(base, f"/v1/threads/{thread_id}/turns", method="POST", body={})

    assert status == 400
    assert "message is required" in json.loads(payload)["error"]


def test_task_queue_lifecycle(fake_home: Path, workspace: Path) -> None:
    with running_server(workspace) as base:
        status, body = call(
            base, "/v1/tasks", method="POST", body={"message": "summarize this repo"}
        )
        assert status == 200
        task_id = json.loads(body)["id"]
        assert json.loads(body)["status"] == "queued"

        status, body = call(base, "/v1/tasks")
        assert status == 200
        assert [task["id"] for task in json.loads(body)["tasks"]] == [task_id]

        status, body = call(base, f"/v1/tasks/{task_id}")
        assert status == 200
        assert json.loads(body)["prompt"] == "summarize this repo"

        status, body = call(base, f"/v1/tasks/{task_id}/cancel", method="POST")
        assert status == 200
        assert json.loads(body)["canceled"] is True


def test_unknown_task_returns_404(fake_home: Path, workspace: Path) -> None:
    with running_server(workspace) as base:
        status, payload = call(base, "/v1/tasks/task_missing")

    assert status == 404
    assert json.loads(payload)["error"] == "not found"


def test_unknown_route_returns_404(fake_home: Path, workspace: Path) -> None:
    with running_server(workspace) as base:
        status, payload = call(base, "/v1/nope")

    assert status == 404


def test_durable_queue_survives_a_restart(fake_home: Path, workspace: Path) -> None:
    with running_server(workspace) as base:
        _, body = call(base, "/v1/tasks", method="POST", body={"message": "persisted"})
        task_id = json.loads(body)["id"]

    with running_server(workspace) as base:
        status, body = call(base, "/v1/tasks")

    assert status == 200
    assert [task["id"] for task in json.loads(body)["tasks"]] == [task_id]
