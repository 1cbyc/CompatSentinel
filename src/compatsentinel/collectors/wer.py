"""New Windows Error Reporting (WER) entries created during the run window.

WER stores one folder per report under ``ReportQueue`` (not yet uploaded) and
``ReportArchive`` (uploaded or kept) in both ``%ProgramData%`` and
``%LOCALAPPDATA%``\\``Microsoft\\Windows\\WER``. Each folder contains
``Report.wer``: a UTF-16 ``key=value`` file whose ``Sig[N].Name`` /
``Sig[N].Value`` pairs carry the crash signature (application name, fault
module, exception code).

Verification status: the parser follows Microsoft's documented layout and is
unit tested against a hand written fixture. WER is disabled on the
development machine (``HKLM\\...\\Windows Error Reporting\\Disabled = 1``), so
no report could be captured there. The Windows CI job prints any report a
hosted runner produces; see docs/DESIGN.md.

Reading ``%ProgramData%`` queues may need elevation on hardened hosts; a
folder that cannot be listed is counted and reported, never fatal.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from compatsentinel.collectors.base import CollectorSkipped, RunContext
from compatsentinel.models import WerReport

REPORT_FILENAME = "Report.wer"
SUBFOLDERS = ("ReportQueue", "ReportArchive")
MTIME_SLACK = timedelta(seconds=30)
"""WER may finish writing a report a little after the app is gone."""

SIGNATURE_NAMES = {
    "app_name": ("Application Name",),
    "app_version": ("Application Version",),
    "fault_module": ("Fault Module Name", "Faulting Module Name"),
    "exception_code": ("Exception Code",),
}


class WerCollector:
    name = "wer"
    requires_elevation = False

    def collect(self, ctx: RunContext) -> list[WerReport]:
        if sys.platform != "win32":
            raise CollectorSkipped("Windows Error Reporting is only available on Windows")
        else:
            return self._collect_windows(ctx)

    def _collect_windows(self, ctx: RunContext) -> list[WerReport]:
        earliest = ctx.started_at
        latest = ctx.finished_at + MTIME_SLACK
        reports: list[WerReport] = []
        denied: list[str] = []

        for folder in report_folders():
            try:
                entries = list(folder.iterdir())
            except FileNotFoundError:
                continue
            except PermissionError:
                denied.append(str(folder))
                continue
            for entry in entries:
                report_file = entry / REPORT_FILENAME
                if not report_file.is_file():
                    continue
                try:
                    modified = datetime.fromtimestamp(entry.stat().st_mtime, tz=UTC)
                    if not earliest <= modified <= latest:
                        continue
                    report = parse_report(read_report(report_file), str(entry), modified)
                except OSError:
                    continue
                if mentions_app(report, ctx.image_names):
                    reports.append(report)

        if denied and not reports:
            # Not an error: the user simply cannot see the machine-wide queue.
            raise CollectorSkipped(f"cannot list {', '.join(denied)} (try an elevated prompt)")
        return sorted(reports, key=lambda r: r.timestamp)


def report_folders() -> list[Path]:
    roots = [os.environ.get("PROGRAMDATA"), os.environ.get("LOCALAPPDATA")]
    return [
        Path(root) / "Microsoft" / "Windows" / "WER" / sub
        for root in roots
        if root
        for sub in SUBFOLDERS
    ]


# --- Pure helpers (unit tested on any OS) ----------------------------------------------


def read_report(path: Path) -> str:
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16").lstrip("\ufeff")
    return raw.decode("utf-8-sig", errors="replace")


def parse_report(text: str, report_path: str, fallback_time: datetime) -> WerReport:
    """Build a :class:`WerReport` from the text of ``Report.wer``."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            fields[key.strip()] = value.strip()

    signature = _signature(fields)
    event_time = parse_filetime(fields.get("EventTime", ""))
    return WerReport(
        report_path=report_path,
        event_type=fields.get("EventType", "") or fields.get("FriendlyEventName", ""),
        app_name=fields.get("AppName") or signature.get("app_name", ""),
        timestamp=event_time or fallback_time,
        app_version=signature.get("app_version") or fields.get("TargetAppVer"),
        fault_module=signature.get("fault_module"),
        exception_code=signature.get("exception_code"),
    )


def mentions_app(report: WerReport, image_names: Iterable[str]) -> bool:
    names = {name.lower() for name in image_names if name}
    app = report.app_name.lower()
    return bool(app) and any(app == name or app.endswith("\\" + name) for name in names)


def parse_filetime(value: str) -> datetime | None:
    """Convert a Windows FILETIME (100 ns ticks since 1601-01-01 UTC) to a datetime.

    ``EventTime`` in ``Report.wer`` is a decimal FILETIME such as
    ``133721760000000000``. Return None for anything that is not a positive
    integer.
    """
    return None  # TODO(juan): implement; see tests/test_wer.py


def _signature(fields: dict[str, str]) -> dict[str, str]:
    """Map ``Sig[N].Name`` labels to their ``Sig[N].Value``."""
    found: dict[str, str] = {}
    for key, label in fields.items():
        if not (key.startswith("Sig[") and key.endswith("].Name")):
            continue
        value = fields.get(key[: -len("Name")] + "Value", "")
        for field_name, labels in SIGNATURE_NAMES.items():
            if label in labels and value:
                found[field_name] = value
    return found
