from __future__ import annotations

from pathlib import Path

import pytest

from vibecli.memory import MemoryManager
from vibecli.rag import CodeIndex


def test_memory_round_trip(tmp_path: Path) -> None:
    manager = MemoryManager(tmp_path / "memory.db", scope=str(tmp_path / "project"))

    memory_id = manager.save("  prefer uv over pip  ")
    entries = manager.list()

    assert memory_id == entries[0].id
    assert entries[0].content == "prefer uv over pip"


def test_memory_is_scoped_per_project(tmp_path: Path) -> None:
    db = tmp_path / "memory.db"
    MemoryManager(db, scope="/project/a").save("fact for a")

    assert MemoryManager(db, scope="/project/b").list() == []
    assert [entry.content for entry in MemoryManager(db, scope="/project/a").list()] == [
        "fact for a"
    ]


def test_memory_search_requires_every_term(tmp_path: Path) -> None:
    manager = MemoryManager(tmp_path / "memory.db", scope="p")
    manager.save("runtime api uses sqlite for durable tasks")
    manager.save("mcp client supports stdio and http")

    assert len(manager.search("sqlite durable")) == 1
    assert manager.search("sqlite mcp") == []
    assert len(manager.search("")) == 2


def test_memory_clear_removes_only_current_scope(tmp_path: Path) -> None:
    db = tmp_path / "memory.db"
    MemoryManager(db, scope="a").save("one")
    MemoryManager(db, scope="b").save("two")

    removed = MemoryManager(db, scope="a").clear()

    assert removed == 1
    assert MemoryManager(db, scope="a").list() == []
    assert len(MemoryManager(db, scope="b").list()) == 1


def test_code_index_rebuild_and_search(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def handler():\n    return 'needle'\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("needle in a non indexed suffix\n", encoding="utf-8")

    index = CodeIndex(tmp_path, db_path=tmp_path / "index.sqlite3")
    count = index.rebuild()
    results = index.search("needle")

    assert count == 2
    assert [Path(result.path) for result in results] == [Path("app.py")]
    assert results[0].line == 2


def test_code_index_skips_ignored_directories(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "keep.py").write_text("target\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.py").write_text("target\n", encoding="utf-8")

    index = CodeIndex(tmp_path, db_path=tmp_path / "index.sqlite3")
    index.rebuild()

    assert [Path(result.path) for result in index.search("target")] == [Path("src") / "keep.py"]


def test_code_index_rebuild_is_idempotent(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("alpha\n", encoding="utf-8")
    index = CodeIndex(tmp_path, db_path=tmp_path / "index.sqlite3")

    first = index.rebuild()
    second = index.rebuild()

    assert first == second == 1
    assert len(index.search("alpha")) == 1


def test_code_index_rejects_paths_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("x\n", encoding="utf-8")
    index = CodeIndex(root, db_path=tmp_path / "index.sqlite3")

    with pytest.raises(ValueError):
        index.rebuild(outside)
