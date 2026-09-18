"""Environment self-check behind ``compatsentinel doctor``.

Everything here is read-only and must run on any OS. The report is a pydantic
model so it can be printed as a table or as JSON with the same data.
"""

from __future__ import annotations

import importlib.util
import platform
import sys

from pydantic import BaseModel, ConfigDict


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
    is_elevated: bool | None = None


def pywin32_available() -> bool:
    """Return True when the ``win32api`` module can be imported.

    ``find_spec`` only locates the module; it does not import it, so this is
    cheap and side-effect free even on Windows.
    """
    return importlib.util.find_spec("win32api") is not None


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
    )
