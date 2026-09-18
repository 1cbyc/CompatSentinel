"""The collector wrapper must never let an exception escape."""

from __future__ import annotations

from datetime import UTC, datetime

from compatsentinel.collectors.base import CollectorSkipped, RunContext, run_collector
from compatsentinel.models import CollectorStatus

CTX = RunContext(
    app_id="x",
    started_at=datetime(2026, 1, 1, tzinfo=UTC),
    finished_at=datetime(2026, 1, 1, tzinfo=UTC),
    pids=(),
    image_names=frozenset({"x.exe"}),
)


class Fine:
    name = "fine"
    requires_elevation = False

    def collect(self, ctx: RunContext) -> list[str]:
        return [ctx.app_id]


class Skips:
    name = "skips"
    requires_elevation = True

    def collect(self, ctx: RunContext) -> list[str]:
        raise CollectorSkipped("needs elevation")


class Explodes:
    name = "explodes"
    requires_elevation = False

    def collect(self, ctx: RunContext) -> list[str]:
        raise RuntimeError("boom")


def test_ok_collector_returns_value_and_timing() -> None:
    value, result = run_collector(Fine(), CTX)
    assert value == ["x"]
    assert result.status is CollectorStatus.OK
    assert result.error is None
    assert result.duration_ms >= 0


def test_skipped_collector_is_not_an_error() -> None:
    value, result = run_collector(Skips(), CTX)
    assert value is None
    assert result.status is CollectorStatus.SKIPPED
    assert result.error == "needs elevation"
    assert result.requires_elevation is True


def test_exception_becomes_error_result() -> None:
    value, result = run_collector(Explodes(), CTX)
    assert value is None
    assert result.status is CollectorStatus.ERROR
    assert result.error == "RuntimeError: boom"
