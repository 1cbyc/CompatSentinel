"""Unit tests for the doctor self-check (pure, OS independent)."""

from __future__ import annotations

import platform
import sys

import pytest

from compatsentinel import doctor


def test_collect_reports_current_interpreter() -> None:
    report = doctor.collect()
    assert report.python_version == platform.python_version()
    assert report.python_executable == sys.executable
    assert report.os_name == platform.system()


def test_capture_supported_only_on_windows() -> None:
    report = doctor.collect()
    assert report.capture_supported is (sys.platform == "win32")


def test_pywin32_available_matches_import(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate a host without pywin32 regardless of what is really installed.
    monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda _name: None)
    assert doctor.pywin32_available() is False


def test_report_is_frozen() -> None:
    report = doctor.collect()
    with pytest.raises(Exception, match="frozen"):
        report.os_name = "Plan9"  # type: ignore[misc]


# --- Juan's Phase 0 task -----------------------------------------------------
# Spec: doctor.is_elevated() -> bool | None
#   * On Windows return True when the current process runs as administrator,
#     False otherwise. Use ctypes.windll.shell32.IsUserAnAdmin(); wrap it so
#     any OSError/AttributeError becomes None instead of an exception.
#   * On any other OS return None ("not applicable"), never False.
#   * collect() must fill DoctorReport.is_elevated with its result.
# Remove the skip markers when done and make these pass on both OSes.


@pytest.mark.skip(reason="TODO(juan): implement doctor.is_elevated()")
def test_is_elevated_is_none_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert doctor.is_elevated() is None


@pytest.mark.skip(reason="TODO(juan): implement doctor.is_elevated()")
@pytest.mark.skipif(sys.platform != "win32", reason="needs Windows")
def test_is_elevated_is_bool_on_windows() -> None:
    assert isinstance(doctor.is_elevated(), bool)


@pytest.mark.skip(reason="TODO(juan): implement doctor.is_elevated()")
def test_collect_fills_is_elevated() -> None:
    report = doctor.collect()
    expected = doctor.is_elevated()
    assert report.is_elevated == expected
