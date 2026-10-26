from __future__ import annotations

import asyncio
from pathlib import Path

from helpers import ScriptedLlm, text_turn, tool_turn

from vibecli.agent import Agent, QueryEngine
from vibecli.config import VibeCliConfig
from vibecli.tools import ToolRegistry, get_builtin_tools


def build_engine(fake_home: Path, workspace: Path, llm: ScriptedLlm) -> QueryEngine:
    registry = ToolRegistry()
    registry.register_all(get_builtin_tools())
    config = VibeCliConfig()
    config.llm.api_key = "test-key"
    config.policy.hitl_mode = "never"
    config.policy.audit_log_path = str(fake_home / "audit.jsonl")
    return QueryEngine(
        llm_client=llm,  # type: ignore[arg-type]
        tool_registry=registry,
        config=config,
        cwd=str(workspace),
    )


def collect(engine: QueryEngine, message: str) -> list[dict]:
    async def run() -> list[dict]:
        return [event async for event in engine.ask(message)]

    return asyncio.run(run())


def test_plain_answer_emits_text_and_done(fake_home: Path, workspace: Path) -> None:
    llm = ScriptedLlm([text_turn("Hello there.")])
    engine = build_engine(fake_home, workspace, llm)

    events = collect(engine, "hi")
    types = [event["type"] for event in events]

    assert "text_delta" in types
    assert types[-1] == "done"
    assert "".join(e["text"] for e in events if e["type"] == "text_delta") == "Hello there."
    assert events[-1]["total_turns"] == 1
    assert events[-1]["total_tokens"] == 15


def test_tool_call_round_trip_reaches_the_model_again(fake_home: Path, workspace: Path) -> None:
    (workspace / "app.py").write_text("print('hi')\n", encoding="utf-8")
    llm = ScriptedLlm(
        [
            tool_turn("read_file", '{"path": "app.py"}'),
            text_turn("The file prints hi."),
        ]
    )
    engine = build_engine(fake_home, workspace, llm)

    events = collect(engine, "read app.py")
    tool_calls = [e for e in events if e["type"] == "tool_call"]
    tool_results = [e for e in events if e["type"] == "tool_result"]

    assert [e["name"] for e in tool_calls] == ["read_file"]
    assert tool_calls[0]["input"] == {"path": "app.py"}
    assert len(tool_results) == 1
    assert tool_results[0]["is_error"] is False
    assert "print('hi')" in tool_results[0]["result"]

    # second model call must carry the assistant tool_calls message and the tool result
    second_messages = llm.received[1]
    assert [m.role for m in second_messages] == ["user", "assistant", "tool"]
    assert second_messages[1].tool_calls[0]["function"]["name"] == "read_file"
    assert second_messages[2].tool_call_id == "call_1"
    assert events[-1]["total_turns"] == 2


def test_streaming_tool_arguments_are_merged(fake_home: Path, workspace: Path) -> None:
    (workspace / "a.txt").write_text("alpha\n", encoding="utf-8")
    llm = ScriptedLlm(
        [
            [
                {
                    "type": "tool_call_delta",
                    "tool_call": {"index": 0, "id": "call_1", "function": {"name": "read_file"}},
                },
                {
                    "type": "tool_call_delta",
                    "tool_call": {"index": 0, "function": {"arguments": '{"path": '}},
                },
                {
                    "type": "tool_call_delta",
                    "tool_call": {"index": 0, "function": {"arguments": '"a.txt"}'}},
                },
                {"type": "message_end", "stop_reason": "tool_use"},
            ],
            text_turn("ok"),
        ]
    )
    engine = build_engine(fake_home, workspace, llm)

    events = collect(engine, "read a.txt")

    assert [e for e in events if e["type"] == "tool_call"][0]["input"] == {"path": "a.txt"}


def test_error_event_stops_the_loop(fake_home: Path, workspace: Path) -> None:
    llm = ScriptedLlm([[{"type": "error", "error": "boom"}]])
    engine = build_engine(fake_home, workspace, llm)

    events = collect(engine, "hi")

    assert [event["type"] for event in events] == ["error"]
    assert events[0]["error"] == "boom"


def test_max_turns_bounds_the_loop(fake_home: Path, workspace: Path) -> None:
    (workspace / "a.txt").write_text("alpha\n", encoding="utf-8")
    llm = ScriptedLlm([tool_turn("read_file", '{"path": "a.txt"}')])

    registry = ToolRegistry()
    registry.register_all(get_builtin_tools())
    config = VibeCliConfig()
    config.llm.api_key = "test-key"
    config.policy.hitl_mode = "never"
    config.policy.audit_log_path = str(fake_home / "audit.jsonl")
    agent = Agent(
        llm_client=llm,  # type: ignore[arg-type]
        tool_registry=registry,
        system_prompt="sys",
        cwd=str(workspace),
        config=config,
        max_turns=3,
    )

    async def run() -> list[dict]:
        return [event async for event in agent.run("loop forever")]

    events = asyncio.run(run())

    assert events[-1]["total_turns"] == 3
    assert llm.calls == 3


def test_agent_takes_pre_and_post_turn_snapshots(fake_home: Path, workspace: Path) -> None:
    (workspace / "seed.txt").write_text("seed\n", encoding="utf-8")
    llm = ScriptedLlm([text_turn("done")])
    engine = build_engine(fake_home, workspace, llm)
    agent = Agent(
        llm_client=engine.llm_client,
        tool_registry=engine.tool_registry,
        system_prompt=engine.system_prompt,
        cwd=str(workspace),
        config=engine.config,
    )

    async def run() -> None:
        async for _ in agent.run("hi"):
            pass

    asyncio.run(run())

    snapshot_root = fake_home / ".vibecli" / "snapshots"
    names = [path.name for path in snapshot_root.glob("*/*")]
    assert any(name.startswith("pre-turn_") for name in names)
    assert any(name.startswith("post-turn_") for name in names)


def test_history_is_preserved_between_runs(fake_home: Path, workspace: Path) -> None:
    llm = ScriptedLlm([text_turn("first"), text_turn("second")])
    engine = build_engine(fake_home, workspace, llm)
    agent = Agent(
        llm_client=engine.llm_client,
        tool_registry=engine.tool_registry,
        system_prompt=engine.system_prompt,
        cwd=str(workspace),
        config=engine.config,
    )

    async def run_twice() -> None:
        async for _ in agent.run("one"):
            pass
        async for _ in agent.run("two"):
            pass

    asyncio.run(run_twice())

    assert [m.role for m in llm.received[1]][:2] == ["user", "assistant"]
    assert llm.received[1][0].content == "one"


def test_system_prompt_lists_tool_contracts(fake_home: Path, workspace: Path) -> None:
    engine = build_engine(fake_home, workspace, ScriptedLlm([text_turn("x")]))

    assert "read_file" in engine.system_prompt
    assert str(workspace) in engine.system_prompt
