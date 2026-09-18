"""Runner: attempt aggregation (pure) and an end-to-end capture with a portable app."""

from __future__ import annotations

import sys

import pytest

from compatsentinel import runner
from compatsentinel.collectors.launch import LaunchAttempt
from compatsentinel.models import CollectorStatus, LaunchOutcome, RunDefaults, Snapshot
from compatsentinel.suite import AppSpec, Suite


def attempt(outcome: LaunchOutcome, startup: float | None = None, **kw: object) -> LaunchAttempt:
    return LaunchAttempt(outcome=outcome, startup_ms=startup, **kw)  # type: ignore[arg-type]


def test_summary_uses_median_and_worst_outcome() -> None:
    signal = runner.summarize_attempts(
        [
            attempt(LaunchOutcome.OK, 400.0, pids=(1,)),
            attempt(LaunchOutcome.EXITED, 900.0, exit_code=1, pids=(2,), error="x"),
            attempt(LaunchOutcome.OK, 500.0, pids=(3,)),
        ]
    )
    assert signal.outcome is LaunchOutcome.EXITED
    assert signal.exit_code == 1
    assert signal.startup_ms == 500.0
    assert signal.startup_samples_ms == [400.0, 900.0, 500.0]
    assert signal.pids == [1, 2, 3]
    assert signal.error == "x"


def test_summary_without_timings() -> None:
    signal = runner.summarize_attempts([attempt(LaunchOutcome.FAILED_TO_START, error="nope")])
    assert signal.startup_ms is None
    assert signal.startup_samples_ms == []


def test_summary_requires_attempts() -> None:
    with pytest.raises(ValueError):
        runner.summarize_attempts([])


def test_capture_end_to_end_with_python_as_the_app() -> None:
    suite = Suite(
        defaults=RunDefaults(timeout_seconds=10, alive_check_seconds=1, repeats=2, warmup_runs=1),
        apps=[
            AppSpec(
                id="sleeper", command=sys.executable, args=["-c", "import time; time.sleep(30)"]
            ),
            AppSpec(id="quitter", command=sys.executable, args=["-c", "raise SystemExit(7)"]),
            AppSpec(id="ghost", command="no-such-binary-xyz.exe"),
        ],
    )
    messages: list[str] = []
    snapshot = runner.capture(
        suite, "test", only=["sleeper", "quitter", "ghost"], progress=messages.append
    )

    assert isinstance(snapshot, Snapshot)
    assert [run.app_id for run in snapshot.apps] == ["sleeper", "quitter", "ghost"]
    assert messages[0] == "fingerprinting environment"
    assert "sleeper: ok" in messages

    sleeper = snapshot.app("sleeper")
    assert sleeper is not None and sleeper.launch is not None
    assert sleeper.launch.outcome is LaunchOutcome.OK
    assert sleeper.modules, "live modules should be collected on the last launch"
    assert {r.name for r in sleeper.collectors} == {"modules", "eventlog", "wer"}

    quitter = snapshot.app("quitter")
    assert quitter is not None and quitter.launch is not None
    assert quitter.launch.outcome is LaunchOutcome.EXITED
    assert quitter.launch.exit_code == 7
    modules_result = next(r for r in quitter.collectors if r.name == "modules")
    assert modules_result.status is CollectorStatus.SKIPPED

    ghost = snapshot.app("ghost")
    assert ghost is not None and ghost.launch is not None
    assert ghost.launch.outcome is LaunchOutcome.FAILED_TO_START

    # Round trip through JSON: the snapshot must be storable as-is.
    assert Snapshot.model_validate_json(snapshot.model_dump_json()) == snapshot


def test_only_filters_apps() -> None:
    suite = Suite(
        defaults=RunDefaults(timeout_seconds=5, alive_check_seconds=1, repeats=1, warmup_runs=0),
        apps=[
            AppSpec(id="a", command="no-such-binary-xyz.exe"),
            AppSpec(id="b", command="no-such-binary-xyz.exe"),
        ],
    )
    snapshot = runner.capture(suite, "x", only=["b"])
    assert [run.app_id for run in snapshot.apps] == ["b"]
