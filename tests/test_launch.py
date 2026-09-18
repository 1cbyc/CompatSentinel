"""Launch collector, driven with the Python interpreter as a portable stand-in app."""

from __future__ import annotations

import subprocess
import sys

import psutil
import pytest

from compatsentinel.collectors.launch import attribute_processes, close, launch
from compatsentinel.models import LaunchOutcome, RunDefaults
from compatsentinel.suite import AppSpec

FAST = RunDefaults(timeout_seconds=10, alive_check_seconds=1, repeats=1, warmup_runs=0)


def python_app(code: str, **overrides: object) -> AppSpec:
    return AppSpec(id="py", command=sys.executable, args=["-c", code], **overrides)  # type: ignore[arg-type]


def test_long_running_app_is_ok_and_closed() -> None:
    attempt = launch(python_app("import time; time.sleep(30)"), FAST)
    try:
        assert attempt.outcome is LaunchOutcome.OK
        assert attempt.alive_after_check is True
        assert attempt.exit_code is None
        assert attempt.pids and all(psutil.pid_exists(pid) for pid in attempt.pids)
        assert attempt.startup_ms is None  # no window regex, so no timing
    finally:
        close(attempt)
    assert attempt.process is not None
    assert attempt.process.poll() is not None


def test_app_that_exits_is_reported_with_exit_code() -> None:
    attempt = launch(python_app("raise SystemExit(3)"), FAST)
    close(attempt)
    assert attempt.outcome is LaunchOutcome.EXITED
    assert attempt.exit_code == 3
    assert attempt.alive_after_check is False


def test_missing_command_fails_to_start() -> None:
    spec = AppSpec(id="nope", command="definitely-not-a-real-command-xyz.exe")
    attempt = launch(spec, FAST)
    close(attempt)
    assert attempt.outcome is LaunchOutcome.FAILED_TO_START
    assert attempt.error is not None
    assert attempt.pids == ()


def test_window_regex_without_window_times_out_quickly() -> None:
    spec = python_app("import time; time.sleep(30)", window_title_regex="NoSuchWindowTitle")
    attempt = launch(spec, RunDefaults(timeout_seconds=2, alive_check_seconds=1))
    try:
        assert attempt.outcome is LaunchOutcome.TIMEOUT
        assert attempt.startup_ms is None
    finally:
        close(attempt)


def test_attribute_processes_includes_children() -> None:
    before = frozenset(psutil.pids())
    parent = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import subprocess, sys, time; "
            "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); time.sleep(30)",
        ]
    )
    try:
        # Give the child a moment to spawn.
        for _ in range(50):
            if psutil.Process(parent.pid).children():
                break
            psutil.time.sleep(0.1)
        owned = attribute_processes(before, parent.pid, "unrelated.exe")
        assert parent.pid in owned
        assert len(owned) >= 2
    finally:
        for proc in psutil.Process(parent.pid).children(recursive=True):
            proc.kill()
        parent.kill()
        parent.wait(5)


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="launches notepad.exe")
def test_notepad_window_is_detected_and_closed() -> None:
    spec = AppSpec(id="notepad", command="notepad.exe", window_title_regex="Notepad")
    attempt = launch(spec, RunDefaults(timeout_seconds=30, alive_check_seconds=2))
    try:
        assert attempt.outcome is LaunchOutcome.OK, attempt
        assert attempt.startup_ms is not None and attempt.startup_ms > 0
        assert attempt.window_title and "Notepad" in attempt.window_title
        assert "notepad.exe" in attempt.image_names
    finally:
        close(attempt)
    assert not any(psutil.pid_exists(pid) for pid in attempt.pids)
