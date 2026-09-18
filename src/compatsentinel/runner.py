"""Orchestrate a capture: environment, then every app, then persist nothing.

The runner owns sequencing and isolation; it does not know how to read a
signal (collectors do) or where snapshots go (the store does). Per app:

1. ``warmup_runs`` untimed launches, then ``repeats`` timed launches.
2. On the last launch, while the app is up, the live collectors run (modules).
3. The app is closed after every launch, whatever happened.
4. The post-run collectors (event log, WER) look at the whole time window.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from compatsentinel import __version__, environment
from compatsentinel.collectors.base import RunContext, run_collector
from compatsentinel.collectors.eventlog import EventLogCollector
from compatsentinel.collectors.launch import LaunchAttempt, close, launch
from compatsentinel.collectors.modules import ModulesCollector
from compatsentinel.collectors.wer import WerCollector
from compatsentinel.models import (
    AppRun,
    CollectorResult,
    CollectorStatus,
    LaunchOutcome,
    LaunchSignal,
    RunDefaults,
    Snapshot,
)
from compatsentinel.suite import AppSpec, Suite

Progress = Callable[[str], None]
"""Callback for one-line status updates; the CLI prints them, tests ignore them."""

SETTLE_SECONDS = 1.0
"""Pause between launches of the same app so a closing instance never races the next one."""

OUTCOME_RANK = {
    LaunchOutcome.OK: 0,
    LaunchOutcome.EXITED: 1,
    LaunchOutcome.TIMEOUT: 2,
    LaunchOutcome.FAILED_TO_START: 3,
}
"""Worse outcomes rank higher; a run reports its worst launch."""


def capture(
    suite: Suite,
    label: str,
    *,
    only: Iterable[str] | None = None,
    progress: Progress = lambda _: None,
) -> Snapshot:
    """Run every app in ``suite`` (or only those in ``only``) and return the snapshot."""
    created_at = _now()
    wanted = set(only) if only is not None else None

    progress("fingerprinting environment")
    env = environment.collect()

    runs: list[AppRun] = []
    for spec in suite.apps:
        if wanted is not None and spec.id not in wanted:
            continue
        progress(f"{spec.id}: launching")
        run = run_app(spec, suite.defaults)
        outcome = run.launch.outcome.value if run.launch else "unknown"
        progress(f"{spec.id}: {outcome}")
        runs.append(run)

    return Snapshot(
        label=label,
        created_at=created_at,
        tool_version=__version__,
        environment=env,
        defaults=suite.defaults,
        apps=runs,
    )


def run_app(spec: AppSpec, defaults: RunDefaults) -> AppRun:
    """Launch one app the configured number of times and gather all its signals."""
    settings = spec.effective(defaults)
    started_at = _now()
    attempts: list[LaunchAttempt] = []
    results: list[CollectorResult] = []
    modules = None
    modules_result: CollectorResult | None = None

    total = settings.warmup_runs + settings.repeats
    for index in range(total):
        attempt = launch(spec, settings)
        try:
            is_last = index == total - 1
            if is_last and attempt.outcome in (LaunchOutcome.OK, LaunchOutcome.TIMEOUT):
                live = RunContext(
                    app_id=spec.id,
                    started_at=started_at,
                    finished_at=_now(),
                    pids=attempt.pids,
                    image_names=attempt.image_names,
                )
                modules, modules_result = run_collector(ModulesCollector(), live)
        finally:
            close(attempt)
        attempts.append(attempt)
        if attempt.outcome is LaunchOutcome.FAILED_TO_START:
            break  # repeating cannot help; do not burn the timeout again
        if not is_last:
            time.sleep(SETTLE_SECONDS)

    if modules_result is None:
        modules_result = CollectorResult(
            name=ModulesCollector.name,
            status=CollectorStatus.SKIPPED,
            error="app was not running after its last launch",
        )
    results.append(modules_result)

    timed = attempts[settings.warmup_runs :] or attempts
    launch_signal = summarize_attempts(timed)
    finished_at = _now()

    post = RunContext(
        app_id=spec.id,
        started_at=started_at,
        finished_at=finished_at,
        pids=tuple(launch_signal.pids),
        image_names=frozenset().union(*(a.image_names for a in attempts)),
    )
    events, events_result = run_collector(EventLogCollector(), post)
    wer, wer_result = run_collector(WerCollector(), post)
    results.extend([events_result, wer_result])

    return AppRun(
        app_id=spec.id,
        command=spec.command,
        args=list(spec.args),
        tags=list(spec.tags),
        started_at=started_at,
        finished_at=finished_at,
        launch=launch_signal,
        modules=modules,
        events=events,
        wer=wer,
        collectors=results,
    )


def summarize_attempts(attempts: list[LaunchAttempt]) -> LaunchSignal:
    """Collapse repeated launches into one signal: worst outcome, median startup."""
    if not attempts:
        raise ValueError("at least one attempt is required")
    worst = max(attempts, key=lambda a: OUTCOME_RANK[a.outcome])
    samples = [round(a.startup_ms, 1) for a in attempts if a.startup_ms is not None]
    pids = sorted({pid for a in attempts for pid in a.pids})
    title = next((a.window_title for a in attempts if a.window_title), None)
    return LaunchSignal(
        outcome=worst.outcome,
        exit_code=worst.exit_code,
        startup_ms=round(statistics.median(samples), 1) if samples else None,
        startup_samples_ms=samples,
        alive_after_check=worst.alive_after_check,
        pids=pids,
        window_title=title,
        error=worst.error,
    )


def _now() -> datetime:
    return datetime.now(UTC)
