"""Collector contract and the safety wrapper that runs one.

A collector observes something about an app run and returns typed data. It
never talks to the runner directly: the runner hands it a :class:`RunContext`
and wraps the call in :func:`run_collector`, which turns any exception into a
:class:`CollectorResult` so one broken signal can never abort a capture.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, TypeVar

from compatsentinel.models import CollectorResult, CollectorStatus

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


class CollectorSkipped(Exception):
    """Raise inside ``collect`` when the signal is not available here.

    Examples: nothing to inspect because the app already exited, or a source
    that needs elevation. This is recorded as ``skipped``, not as an error.
    """


@dataclass(frozen=True)
class RunContext:
    """What a collector may know about the run it is observing."""

    app_id: str
    started_at: datetime
    """UTC, taken just before the first launch."""
    finished_at: datetime
    """UTC, taken when the context was built (after close for post-run collectors)."""
    pids: tuple[int, ...]
    """Process ids attributed to the app. Alive for live collectors, historical otherwise."""
    image_names: frozenset[str]
    """Lowercase executable names attributed to the app, e.g. ``{"notepad.exe"}``."""


class Collector(Protocol[T_co]):
    """Anything with a name and a ``collect`` method.

    Implementations are plain classes; they do not inherit from this. That is
    a structural interface: if it quacks, it is a collector.
    """

    name: str
    requires_elevation: bool

    def collect(self, ctx: RunContext) -> T_co: ...


def run_collector(collector: Collector[T], ctx: RunContext) -> tuple[T | None, CollectorResult]:
    """Run ``collector`` and report how it went. Never raises."""
    start = time.perf_counter()
    value: T | None = None
    status = CollectorStatus.OK
    error: str | None = None
    try:
        value = collector.collect(ctx)
    except CollectorSkipped as exc:
        status = CollectorStatus.SKIPPED
        error = str(exc) or None
    except Exception as exc:
        status = CollectorStatus.ERROR
        error = f"{type(exc).__name__}: {exc}"
    duration_ms = (time.perf_counter() - start) * 1000
    result = CollectorResult(
        name=collector.name,
        status=status,
        duration_ms=round(duration_ms, 1),
        error=error,
        requires_elevation=collector.requires_elevation,
    )
    return value, result
