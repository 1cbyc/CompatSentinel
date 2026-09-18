"""WER report parsing against a hand written Report.wer fixture.

The fixture mirrors the documented layout of an APPCRASH report. It was not
recorded from a live machine (see the module docstring in wer.py).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from compatsentinel.collectors import wer

FALLBACK = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)

REPORT = """Version=1
EventType=APPCRASH
EventTime=133721760000000000
ReportType=2
Consent=1
UploadTime=133721760050000000
ReportStatus=268435456
ReportIdentifier=3c2b5a1e-0000-4000-8000-000000000001
Sig[0].Name=Application Name
Sig[0].Value=Contoso.App.exe
Sig[1].Name=Application Version
Sig[1].Value=3.2.1.0
Sig[2].Name=Application Timestamp
Sig[2].Value=66f2a1b3
Sig[3].Name=Fault Module Name
Sig[3].Value=KERNELBASE.dll
Sig[4].Name=Fault Module Version
Sig[4].Value=10.0.26100.4351
Sig[6].Name=Exception Code
Sig[6].Value=e06d7363
DynamicSig[1].Name=OS Version
DynamicSig[1].Value=10.0.26100.2.0.0.256.48
FriendlyEventName=Stopped working
AppName=Contoso App
AppPath=C:\\Program Files\\Contoso\\Contoso.App.exe
"""


def test_parse_report_extracts_signature() -> None:
    report = wer.parse_report(REPORT, r"C:\WER\AppCrash_Contoso", FALLBACK)
    assert report.event_type == "APPCRASH"
    assert report.app_name == "Contoso App"
    assert report.app_version == "3.2.1.0"
    assert report.fault_module == "KERNELBASE.dll"
    assert report.exception_code == "e06d7363"
    assert report.report_path == r"C:\WER\AppCrash_Contoso"


def test_parse_report_falls_back_to_signature_and_mtime() -> None:
    minimal = "EventType=APPCRASH\nSig[0].Name=Application Name\nSig[0].Value=x.exe\n"
    report = wer.parse_report(minimal, "p", FALLBACK)
    assert report.app_name == "x.exe"
    assert report.timestamp == FALLBACK  # no parsable EventTime
    assert report.fault_module is None


def test_read_report_handles_utf16_and_utf8(tmp_path: Path) -> None:
    utf16 = tmp_path / "a.wer"
    utf16.write_bytes("EventType=APPCRASH\n".encode("utf-16"))  # encode adds the BOM
    utf8 = tmp_path / "b.wer"
    utf8.write_bytes(b"EventType=APPHANG\n")
    assert wer.read_report(utf16).strip() == "EventType=APPCRASH"
    assert wer.read_report(utf8).strip() == "EventType=APPHANG"


def test_mentions_app_matches_name_or_path_tail() -> None:
    report = wer.parse_report(REPORT, "p", FALLBACK)
    assert not wer.mentions_app(report, {"contoso.app.exe"})  # AppName is the friendly name
    by_signature = report.model_copy(update={"app_name": "Contoso.App.exe"})
    assert wer.mentions_app(by_signature, {"contoso.app.exe"})
    with_path = report.model_copy(update={"app_name": r"C:\x\Contoso.App.exe"})
    assert wer.mentions_app(with_path, {"contoso.app.exe"})
    assert not wer.mentions_app(with_path, {"notepad.exe"})


def test_report_folders_come_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # Uppercase on purpose: Windows ignores case, Linux (where CI runs) does not.
    monkeypatch.setenv("PROGRAMDATA", r"C:\ProgramData")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\me\AppData\Local")
    folders = [str(p) for p in wer.report_folders()]
    assert len(folders) == 4
    assert any(f.endswith("ReportQueue") and "ProgramData" in f for f in folders)
    assert any(f.endswith("ReportArchive") and "AppData" in f for f in folders)


# --- Juan's Phase 2 task (optional) -------------------------------------------------
# Spec: parse_filetime(value: str) -> datetime | None
#   * A FILETIME counts 100-nanosecond ticks since 1601-01-01T00:00:00 UTC.
#   * Convert via datetime(1601, 1, 1, tzinfo=UTC) + timedelta(microseconds=ticks // 10).
#   * Return None when value is empty, not an integer, or not positive.
# Until done, report timestamps fall back to the folder's modification time.


@pytest.mark.skip(reason="TODO(juan): implement parse_filetime")
def test_parse_filetime() -> None:
    # 133721760000000000 ticks -> 2024-10-16 08:00:00 UTC
    assert wer.parse_filetime("133721760000000000") == datetime(2024, 10, 16, 8, 0, tzinfo=UTC)
    assert wer.parse_filetime("") is None
    assert wer.parse_filetime("abc") is None
    assert wer.parse_filetime("-5") is None


@pytest.mark.skip(reason="TODO(juan): implement parse_filetime")
def test_parse_report_uses_event_time_when_present() -> None:
    report = wer.parse_report(REPORT, "p", FALLBACK)
    assert report.timestamp == datetime(2024, 10, 16, 8, 0, tzinfo=UTC)
