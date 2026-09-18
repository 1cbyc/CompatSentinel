"""Builders for test data. Plain functions, importable from any test module."""

from __future__ import annotations

from datetime import UTC, datetime

from compatsentinel.models import (
    AppRun,
    Environment,
    EventLogEntry,
    LaunchOutcome,
    LaunchSignal,
    ModuleInfo,
    Snapshot,
    WerReport,
)

FIXED_TIME = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)

SYSTEM_MODULES = [
    ModuleInfo(
        name="ntdll.dll",
        path=r"C:\Windows\System32\ntdll.dll",
        version="10.0.26100.4351",
        is_system=True,
    ),
    ModuleInfo(
        name="KERNELBASE.dll",
        path=r"C:\Windows\System32\KERNELBASE.dll",
        version="10.0.26100.4351",
        is_system=True,
    ),
]
APP_MODULES = [
    ModuleInfo(name="App.exe", path=r"C:\Program Files\Contoso\App.exe", version="3.2.1.0"),
    ModuleInfo(
        name="Contoso.Core.dll",
        path=r"C:\Program Files\Contoso\Contoso.Core.dll",
        version="3.2.1.0",
    ),
]


def make_environment(**overrides: object) -> Environment:
    fields: dict[str, object] = {
        "os_name": "Windows 11",
        "os_version": "10.0.26100",
        "architecture": "AMD64",
        "python_version": "3.11.1",
        "build": 26100,
        "ubr": 4351,
        "display_version": "24H2",
        "edition": "Professional",
        "hotfixes": ["KB5043080", "KB5044284"],
    }
    return Environment.model_validate(fields | overrides)


def make_launch(
    outcome: LaunchOutcome = LaunchOutcome.OK,
    startup_ms: float | None = 400.0,
    exit_code: int | None = 0,
    **overrides: object,
) -> LaunchSignal:
    fields: dict[str, object] = {
        "outcome": outcome,
        "startup_ms": startup_ms,
        "startup_samples_ms": [startup_ms] if startup_ms is not None else [],
        "exit_code": exit_code,
        "alive_after_check": outcome is LaunchOutcome.OK,
        "pids": [4321],
        "window_title": "Untitled - App",
    }
    return LaunchSignal.model_validate(fields | overrides)


def make_run(
    app_id: str = "app",
    launch: LaunchSignal | None = None,
    modules: list[ModuleInfo] | None = None,
    events: list[EventLogEntry] | None = None,
    wer: list[WerReport] | None = None,
    *,
    no_modules: bool = False,
    no_events: bool = False,
    no_wer: bool = False,
) -> AppRun:
    """A healthy run by default. ``no_*`` flags make that signal ``None`` (collector absent)."""
    return AppRun(
        app_id=app_id,
        command=f"{app_id}.exe",
        started_at=FIXED_TIME,
        finished_at=FIXED_TIME,
        launch=launch if launch is not None else make_launch(),
        modules=None
        if no_modules
        else (modules if modules is not None else SYSTEM_MODULES + APP_MODULES),
        events=None if no_events else (events or []),
        wer=None if no_wer else (wer or []),
    )


def make_event(
    source: str = "Contoso Service",
    event_id: int = 4242,
    message: str = "Contoso.App.exe: configuration file missing",
    level: str = "error",
) -> EventLogEntry:
    return EventLogEntry(
        log="Application",
        source=source,
        event_id=event_id,
        level=level,
        timestamp=FIXED_TIME,
        message=message,
    )


def make_wer(
    app_name: str = "App.exe",
    fault_module: str | None = "Contoso.Core.dll",
    exception_code: str | None = "c0000005",
) -> WerReport:
    return WerReport(
        report_path=r"C:\ProgramData\Microsoft\Windows\WER\ReportArchive\AppCrash_App.exe_1",
        event_type="APPCRASH",
        app_name=app_name,
        timestamp=FIXED_TIME,
        app_version="3.2.1.0",
        fault_module=fault_module,
        exception_code=exception_code,
    )


def make_snapshot(
    label: str = "before",
    apps: list[AppRun] | None = None,
    environment: Environment | None = None,
) -> Snapshot:
    return Snapshot(
        label=label,
        created_at=FIXED_TIME,
        tool_version="0.1.0.dev0",
        environment=environment or make_environment(),
        apps=apps if apps is not None else [make_run("notepad")],
    )
