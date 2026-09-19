"""Snapshot store tests: persistence, lookup and schema guarding."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from compatsentinel.store import (
    SNAPSHOT_FILENAME,
    InvalidLabelError,
    SchemaVersionError,
    SnapshotExistsError,
    SnapshotNotFoundError,
    SnapshotStore,
    StoreError,
)
from tests.conftest import SnapshotFactory


@pytest.fixture
def store(tmp_path: Path) -> SnapshotStore:
    return SnapshotStore(tmp_path / "snapshots")


def test_save_then_load_round_trips(store: SnapshotStore, make_snapshot: SnapshotFactory) -> None:
    snapshot = make_snapshot(label="before")
    path = store.save(snapshot)
    assert path == store.root / "before" / SNAPSHOT_FILENAME
    assert path.is_file()
    assert not path.with_suffix(".json.tmp").exists()
    assert store.load("before") == snapshot


def test_saved_json_is_readable_and_versioned(
    store: SnapshotStore, make_snapshot: SnapshotFactory
) -> None:
    path = store.save(make_snapshot())
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["apps"][0]["app_id"] == "notepad"


def test_refuses_to_overwrite_unless_asked(
    store: SnapshotStore, make_snapshot: SnapshotFactory
) -> None:
    store.save(make_snapshot())
    with pytest.raises(SnapshotExistsError, match="already exists"):
        store.save(make_snapshot())
    store.save(make_snapshot(tool_version="9.9.9"), overwrite=True)
    assert store.load("before").tool_version == "9.9.9"


def test_missing_label_is_a_clear_error(store: SnapshotStore) -> None:
    with pytest.raises(SnapshotNotFoundError, match="'after' not found"):
        store.load("after")


def test_invalid_label_is_rejected_before_touching_disk(store: SnapshotStore) -> None:
    with pytest.raises(InvalidLabelError):
        store.path_for("../escape")
    with pytest.raises(InvalidLabelError):
        store.path_for("")


def test_load_accepts_directory_and_file_paths(
    store: SnapshotStore, make_snapshot: SnapshotFactory, tmp_path: Path
) -> None:
    path = store.save(make_snapshot(label="elsewhere"))
    assert store.load(path) == store.load(path.parent) == store.load("elsewhere")
    other = SnapshotStore(tmp_path / "other-root")
    assert other.load(path.parent).label == "elsewhere"  # path wins over label lookup


def test_newer_schema_is_refused(store: SnapshotStore, make_snapshot: SnapshotFactory) -> None:
    path = store.save(make_snapshot())
    data = json.loads(path.read_text(encoding="utf-8"))
    data["schema_version"] = 99
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SchemaVersionError, match="newer than"):
        store.load("before")


def test_corrupt_file_is_reported(store: SnapshotStore) -> None:
    path = store.path_for("broken")
    path.parent.mkdir(parents=True)
    path.write_text('{"label": "broken"}', encoding="utf-8")
    with pytest.raises(StoreError, match="not a valid snapshot"):
        store.load("broken")


# NOTE: list_labels was originally left as a task for Juan, with the spec and
# hints below. It was implemented ahead of schedule in Phase 5 because the MCP
# server's list_snapshots tool depends on it; see docs/DESIGN.md.
#
# Spec: SnapshotStore.list_labels() -> list[str]
#   * Return the names of the directories directly under self.root that contain
#     a snapshot.json file, sorted alphabetically.
#   * Ignore files and directories without snapshot.json (e.g. a leftover
#     .json.tmp directory or a README).
#   * If self.root does not exist, return [] rather than raising.


def test_list_labels_sorted(store: SnapshotStore, make_snapshot: SnapshotFactory) -> None:
    for label in ("zeta", "alpha", "mid"):
        store.save(make_snapshot(label=label))
    (store.root / "not-a-snapshot").mkdir()
    (store.root / "stray.txt").write_text("x", encoding="utf-8")
    assert store.list_labels() == ["alpha", "mid", "zeta"]


def test_list_labels_missing_root(tmp_path: Path) -> None:
    assert SnapshotStore(tmp_path / "does-not-exist").list_labels() == []
