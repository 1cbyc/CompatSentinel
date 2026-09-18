"""Windows-only end-to-end capture of notepad: the Phase 2 acceptance test.

Runs on a real Windows host (GitHub's ``windows-latest`` in CI). Everything
it exercises is also unit tested with the Python interpreter as a stand-in
app; this test proves the Windows-specific parts (window detection, DLL
enumeration, event log query) against the real OS.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from compatsentinel import runner
from compatsentinel.models import CollectorStatus, LaunchOutcome, RunDefaults
from compatsentinel.store import SnapshotStore
from compatsentinel.suite import AppSpec, Suite

pytestmark = [
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="launches notepad.exe"),
]


def test_capture_notepad_produces_a_valid_snapshot(tmp_path: Path) -> None:
    suite = Suite(
        defaults=RunDefaults(timeout_seconds=30, alive_check_seconds=2, repeats=2, warmup_runs=1),
        apps=[AppSpec(id="notepad", command="notepad.exe", window_title_regex="Notepad")],
    )
    snapshot = runner.capture(suite, "ci")

    run = snapshot.app("notepad")
    assert run is not None and run.launch is not None
    assert run.launch.outcome is LaunchOutcome.OK, run.launch
    assert run.launch.startup_ms is not None and run.launch.startup_ms > 0
    assert len(run.launch.startup_samples_ms) == 2
    assert run.launch.window_title

    assert run.modules, "notepad must have loaded DLLs"
    assert any(m.is_system for m in run.modules), "expected at least one System32 DLL"

    statuses = {r.name: r.status for r in run.collectors}
    assert statuses["modules"] is CollectorStatus.OK
    assert statuses["eventlog"] is CollectorStatus.OK, run.collectors
    assert run.events == []  # a clean notepad launch raises no errors

    assert snapshot.environment.build is not None
    assert snapshot.environment.os_name.startswith("Windows")

    store = SnapshotStore(tmp_path / "snapshots")
    path = store.save(snapshot)
    assert store.load("ci") == snapshot
    assert path.stat().st_size > 1000
