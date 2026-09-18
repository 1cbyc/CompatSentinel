"""Environment self-check behind ``compatsentinel doctor``.

Everything here is read-only and must run on any OS. The report is a pydantic
model so it can be printed as a table or as JSON with the same data.
"""

from __future__ import annotations

import importlib.util
import platform
import sys

from pydantic import BaseModel, ConfigDict

WER_KEY = r"SOFTWARE\Microsoft\Windows\Windows Error Reporting"
WER_POLICY_KEY = r"SOFTWARE\Policies\Microsoft\Windows\Windows Error Reporting"


class DoctorReport(BaseModel):
    """What ``doctor`` learned about the host."""

    model_config = ConfigDict(frozen=True)

    python_version: str
    python_executable: str
    os_name: str
    os_release: str
    os_version: str
    machine: str
    pywin32_available: bool
    capture_supported: bool
    wer_enabled: bool | None = None
    """None off Windows. False means crash reports and Application Error events never appear."""
    is_elevated: bool | None = None


def pywin32_available() -> bool:
    """Return True when the ``win32api`` module can be imported.

    ``find_spec`` only locates the module; it does not import it, so this is
    cheap and side-effect free even on Windows.
    """
    return importlib.util.find_spec("win32api") is not None


def wer_enabled() -> bool | None:
    """Whether Windows Error Reporting is enabled, or None off Windows.

    WER is off when ``Disabled`` is 1 under the machine key, the user key or
    the policy key. Any of those silences both ``Report.wer`` files and the
    ``Application Error`` events that CompatSentinel uses to detect crashes.
    """
    if sys.platform != "win32":
        return None
    else:
        import winreg

        locations = (
            (winreg.HKEY_LOCAL_MACHINE, WER_POLICY_KEY),
            (winreg.HKEY_LOCAL_MACHINE, WER_KEY),
            (winreg.HKEY_CURRENT_USER, WER_KEY),
        )
        for root, path in locations:
            try:
                with winreg.OpenKey(root, path) as key:
                    value, _ = winreg.QueryValueEx(key, "Disabled")
            except OSError:
                continue
            if value == 1:
                return False
        return True


def collect() -> DoctorReport:
    """Gather the doctor report for the current host."""
    os_name = platform.system()
    return DoctorReport(
        python_version=platform.python_version(),
        python_executable=sys.executable,
        os_name=os_name,
        os_release=platform.release(),
        os_version=platform.version(),
        machine=platform.machine(),
        pywin32_available=pywin32_available(),
        capture_supported=os_name == "Windows",
        wer_enabled=wer_enabled(),
    )
