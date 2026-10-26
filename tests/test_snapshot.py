from __future__ import annotations

from pathlib import Path

import pytest

from vibecli.snapshot import SnapshotService


def test_snapshot_is_stored_outside_the_workspace(fake_home: Path, workspace: Path) -> None:
    (workspace / "a.txt").write_text("one", encoding="utf-8")
    service = SnapshotService(workspace)

    record = service.create("pre-turn")

    assert record.path.is_dir()
    assert (record.path / "a.txt").read_text(encoding="utf-8") == "one"
    assert fake_home in record.path.parents
    assert not (workspace / ".vibecli" / "snapshots").exists()


def test_snapshot_skips_heavy_directories(fake_home: Path, workspace: Path) -> None:
    (workspace / "keep.txt").write_text("keep", encoding="utf-8")
    for name in (".git", "node_modules", "__pycache__"):
        (workspace / name).mkdir()
        (workspace / name / "junk.txt").write_text("junk", encoding="utf-8")

    record = SnapshotService(workspace).create("pre-turn")

    assert (record.path / "keep.txt").exists()
    for name in (".git", "node_modules", "__pycache__"):
        assert not (record.path / name).exists()


def test_restore_brings_back_previous_content(fake_home: Path, workspace: Path) -> None:
    (workspace / "a.txt").write_text("original", encoding="utf-8")
    service = SnapshotService(workspace)
    service.create("pre-turn")

    (workspace / "a.txt").write_text("mutated", encoding="utf-8")
    (workspace / "added.txt").write_text("added", encoding="utf-8")

    service.restore("1")

    assert (workspace / "a.txt").read_text(encoding="utf-8") == "original"
    assert not (workspace / "added.txt").exists()


def test_restore_by_id_and_index_are_equivalent(fake_home: Path, workspace: Path) -> None:
    (workspace / "a.txt").write_text("v1", encoding="utf-8")
    service = SnapshotService(workspace)
    first = service.create("pre-turn")
    (workspace / "a.txt").write_text("v2", encoding="utf-8")
    second = service.create("post-turn")

    records = service.list()
    assert [record.id for record in records] == [second.id, first.id]

    service.restore(first.id)
    assert (workspace / "a.txt").read_text(encoding="utf-8") == "v1"


def test_restore_takes_its_own_safety_snapshot(fake_home: Path, workspace: Path) -> None:
    (workspace / "a.txt").write_text("v1", encoding="utf-8")
    service = SnapshotService(workspace)
    service.create("pre-turn")
    (workspace / "a.txt").write_text("v2", encoding="utf-8")

    service.restore("1")

    assert [record.phase for record in service.list()][0] == "pre-restore"


def test_restore_unknown_reference_raises(fake_home: Path, workspace: Path) -> None:
    service = SnapshotService(workspace)
    service.create("pre-turn")

    with pytest.raises(ValueError):
        service.restore("99")
    with pytest.raises(ValueError):
        service.restore("does-not-exist")


def test_clean_removes_every_snapshot(fake_home: Path, workspace: Path) -> None:
    (workspace / "a.txt").write_text("x", encoding="utf-8")
    service = SnapshotService(workspace)
    service.create("pre-turn")
    service.create("post-turn")

    removed = service.clean()

    assert removed == 2
    assert service.list() == []


def test_snapshots_are_isolated_per_project(fake_home: Path, tmp_path: Path) -> None:
    first = tmp_path / "project-a"
    second = tmp_path / "project-b"
    for path in (first, second):
        path.mkdir()
        (path / "f.txt").write_text(path.name, encoding="utf-8")

    SnapshotService(first).create("pre-turn")

    assert len(SnapshotService(first).list()) == 1
    assert SnapshotService(second).list() == []
