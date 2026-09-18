"""Windows-only smoke test: prove CI can launch and close a GUI app.

This is the seed of the Phase 2 launch collector. Two facts drive its shape:

* On Windows 11 ``notepad.exe`` in System32 is a stub that exits with code 0
  almost immediately and starts the packaged ``Notepad.exe`` under a new PID.
  On Windows Server (GitHub's ``windows-latest``) it is the classic Win32 app
  and the PID we spawned stays alive.
* We therefore track *new* processes by image name rather than trusting the
  PID returned by ``Popen``, and we only close PIDs that did not exist before.
"""

from __future__ import annotations

import csv
import io
import subprocess
import sys
import time

import pytest

pytestmark = [
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="launches notepad.exe"),
]

IMAGE = "notepad.exe"


def _pids(image: str) -> set[int]:
    """PIDs of running processes whose image name matches (case-insensitive)."""
    out = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    if "No tasks" in out:
        return set()
    return {int(row[1]) for row in csv.reader(io.StringIO(out)) if len(row) > 1}


def test_notepad_launches_and_can_be_closed() -> None:
    before = _pids(IMAGE)
    proc = subprocess.Popen([IMAGE])
    new: set[int] = set()
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            new = _pids(IMAGE) - before
            if new or (proc.poll() is None and time.monotonic() > deadline - 12):
                break
            time.sleep(0.25)
        alive_ourselves = proc.poll() is None
        assert new or alive_ourselves, "no notepad process appeared within 15s"
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
        for pid in new:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, check=False)

    time.sleep(1)
    assert not (_pids(IMAGE) - before), "notepad we started is still running"
