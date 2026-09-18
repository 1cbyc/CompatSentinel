"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from typer.testing import CliRunner

from compatsentinel.models import (
    AppRun,
    Environment,
    LaunchOutcome,
    LaunchSignal,
    ModuleInfo,
    Snapshot,
)

FIXED_TIME = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)

SnapshotFactory = Callable[..., Snapshot]


@pytest.fixture
def runner() -> CliRunner:
    """A Click/Typer test runner that captures output without spawning a process."""
    return CliRunner()


@pytest.fixture
def environment() -> Environment:
    return Environment(
        os_name="Windows",
        os_version="10.0.26100",
        architecture="AMD64",
        python_version="3.11.1",
        build=26100,
        ubr=4351,
        display_version="24H2",
        edition="Professional",
        hotfixes=["KB5043080", "KB5044284"],
    )


@pytest.fixture
def make_snapshot(environment: Environment) -> SnapshotFactory:
    """Factory fixture: ``make_snapshot(label="before", apps=[...])``."""

    def _make(
        label: str = "before", apps: list[AppRun] | None = None, **overrides: object
    ) -> Snapshot:
        if apps is None:
            apps = [
                AppRun(
                    app_id="notepad",
                    command="notepad.exe",
                    started_at=FIXED_TIME,
                    finished_at=FIXED_TIME,
                    launch=LaunchSignal(
                        outcome=LaunchOutcome.OK,
                        startup_ms=412.0,
                        startup_samples_ms=[398.0, 412.0, 450.0],
                        alive_after_check=True,
                        pids=[4321],
                        window_title="Untitled - Notepad",
                    ),
                    modules=[
                        ModuleInfo(
                            name="ntdll.dll",
                            path=r"C:\Windows\System32\ntdll.dll",
                            version="10.0.26100.4351",
                            is_system=True,
                        )
                    ],
                    events=[],
                    wer=[],
                )
            ]
        fields: dict[str, object] = {
            "label": label,
            "created_at": FIXED_TIME,
            "tool_version": "0.1.0.dev0",
            "environment": environment,
            "apps": apps,
        }
        return Snapshot.model_validate(fields | overrides)

    return _make
