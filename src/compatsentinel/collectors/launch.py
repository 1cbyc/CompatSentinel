"""Start an app, find its window, time the startup, decide the outcome, close it.

Process attribution is the hard part. A command such as ``notepad.exe`` may be
a stub that exits at once and hands over to a packaged app under a new PID
that is not even its child. So an app run "owns" the union of:

* the process we spawned and its descendants,
* new processes (not running before launch) whose image name matches the
  command's file name,
* new processes that own a top-level window matching ``window_title_regex``.

Only processes attributed this way are ever closed. Pre-existing windows of
the same app are never touched.
"""

from __future__ import annotations

import contextlib
import re
import subprocess
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import PureWindowsPath

import psutil

from compatsentinel.models import LaunchOutcome, RunDefaults
from compatsentinel.suite import AppSpec

POLL_INTERVAL_SECONDS = 0.05
EXIT_GRACE_SECONDS = 2.0
"""How long to keep looking after a zero exit before calling it 'exited'."""
CLOSE_TIMEOUT_SECONDS = 10.0
TERMINATE_TIMEOUT_SECONDS = 3.0


@dataclass(frozen=True)
class WindowInfo:
    hwnd: int
    pid: int
    title: str


@dataclass
class LaunchAttempt:
    """Result of one launch, plus the handles needed to inspect and close it."""

    outcome: LaunchOutcome
    pids: tuple[int, ...] = ()
    image_names: frozenset[str] = frozenset()
    windows: tuple[WindowInfo, ...] = ()
    startup_ms: float | None = None
    exit_code: int | None = None
    alive_after_check: bool | None = None
    error: str | None = None
    process: subprocess.Popen[bytes] | None = field(default=None, repr=False)

    @property
    def window_title(self) -> str | None:
        return self.windows[0].title if self.windows else None


def launch(spec: AppSpec, settings: RunDefaults) -> LaunchAttempt:
    """Start ``spec`` and watch it for up to ``timeout + alive_check`` seconds.

    The caller is responsible for :func:`close` afterwards, whatever the outcome.
    """
    before = frozenset(psutil.pids())
    pattern = re.compile(spec.window_title_regex) if spec.window_title_regex else None
    image = PureWindowsPath(spec.command).name.lower()

    started = time.perf_counter()
    try:
        process = subprocess.Popen([spec.command, *spec.args])
    except OSError as exc:
        return LaunchAttempt(
            outcome=LaunchOutcome.FAILED_TO_START, error=f"{type(exc).__name__}: {exc}"
        )

    deadline = started + settings.timeout_seconds
    windows: tuple[WindowInfo, ...] = ()
    startup_ms: float | None = None
    first_zero_exit: float | None = None
    pids: tuple[int, ...] = (process.pid,)

    while True:
        now = time.perf_counter()
        if pattern is not None:
            windows = find_windows(pattern, exclude=before)
            if windows:
                startup_ms = (now - started) * 1000
                break
        else:
            break  # no window to wait for; the alive check decides

        exit_code = process.poll()
        if exit_code is not None:
            pids = attribute_processes(before, process.pid, image)
            if not pids:
                if exit_code != 0:
                    break
                first_zero_exit = first_zero_exit or now
                if now - first_zero_exit >= EXIT_GRACE_SECONDS:
                    break
        if now >= deadline:
            break
        time.sleep(POLL_INTERVAL_SECONDS)

    pids = _merge(attribute_processes(before, process.pid, image), (w.pid for w in windows))
    image_names = _image_names(pids) | {image}

    if pattern is not None and not windows:
        exit_code = process.poll()
        outcome = LaunchOutcome.TIMEOUT if _alive(pids) else LaunchOutcome.EXITED
        return LaunchAttempt(
            outcome=outcome,
            pids=pids,
            image_names=image_names,
            exit_code=exit_code,
            alive_after_check=False,
            error=None
            if outcome is LaunchOutcome.TIMEOUT
            else "no matching window; process exited",
            process=process,
        )

    time.sleep(settings.alive_check_seconds)
    pids = _merge(pids, attribute_processes(before, process.pid, image))
    alive = _alive(pids)
    return LaunchAttempt(
        outcome=LaunchOutcome.OK if alive else LaunchOutcome.EXITED,
        pids=pids,
        image_names=image_names | _image_names(pids),
        windows=windows,
        startup_ms=startup_ms,
        exit_code=process.poll(),
        alive_after_check=alive,
        process=process,
    )


def close(attempt: LaunchAttempt) -> None:
    """Close everything the attempt owns: WM_CLOSE first, then terminate, then kill."""
    procs = _processes(attempt.pids)
    if attempt.process is not None and attempt.process.poll() is None:
        procs.append(psutil.Process(attempt.process.pid))
    if not procs:
        return

    for window in windows_for_pids({p.pid for p in procs}):
        _post_close(window.hwnd)
    _, alive = psutil.wait_procs(procs, timeout=CLOSE_TIMEOUT_SECONDS)
    for proc in alive:
        _ignore_gone(proc.terminate)
    _, alive = psutil.wait_procs(alive, timeout=TERMINATE_TIMEOUT_SECONDS)
    for proc in alive:
        _ignore_gone(proc.kill)
    process = attempt.process
    if process is not None:
        _ignore_gone(lambda: process.wait(timeout=TERMINATE_TIMEOUT_SECONDS))


# --- Attribution ---------------------------------------------------------------


def attribute_processes(before: frozenset[int], root_pid: int, image: str) -> tuple[int, ...]:
    """Live PIDs that belong to the launch: the spawned tree plus new same-image processes."""
    owned: set[int] = set()
    try:
        root = psutil.Process(root_pid)
        if root.is_running() and root.status() != psutil.STATUS_ZOMBIE:
            owned.add(root_pid)
            owned.update(child.pid for child in root.children(recursive=True))
    except psutil.Error:
        pass
    for proc in psutil.process_iter(["pid", "name"]):
        if proc.pid in before or proc.pid in owned:
            continue
        if (proc.info["name"] or "").lower() == image:
            owned.add(proc.pid)
    return tuple(sorted(owned))


def _processes(pids: tuple[int, ...]) -> list[psutil.Process]:
    procs: list[psutil.Process] = []
    for pid in pids:
        try:
            proc = psutil.Process(pid)
            if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
                procs.append(proc)
        except psutil.Error:
            continue
    return procs


def _alive(pids: tuple[int, ...]) -> bool:
    return bool(_processes(pids))


def _image_names(pids: tuple[int, ...]) -> frozenset[str]:
    names: set[str] = set()
    for proc in _processes(pids):
        try:
            names.add(proc.name().lower())
        except psutil.Error:
            continue
    return frozenset(names)


def _merge(*groups: Iterable[int]) -> tuple[int, ...]:
    merged: set[int] = set()
    for group in groups:
        merged.update(group)
    return tuple(sorted(merged))


def _ignore_gone(action: Callable[[], object]) -> None:
    with contextlib.suppress(psutil.Error, subprocess.TimeoutExpired):
        action()


# --- Windows-only window helpers ---------------------------------------------------
# pywin32 is imported inside these functions so this module imports on any OS.


def find_windows(pattern: re.Pattern[str], exclude: frozenset[int]) -> tuple[WindowInfo, ...]:
    """Visible top-level windows whose title matches, owned by a PID not in ``exclude``."""
    if sys.platform != "win32":
        return ()
    else:
        return tuple(
            w for w in _enumerate_windows() if w.pid not in exclude and pattern.search(w.title)
        )


def windows_for_pids(pids: set[int]) -> tuple[WindowInfo, ...]:
    """Every visible top-level window owned by one of ``pids``."""
    if sys.platform != "win32" or not pids:
        return ()
    else:
        return tuple(w for w in _enumerate_windows() if w.pid in pids)


def _enumerate_windows() -> list[WindowInfo]:
    """Every visible top-level window with a non-empty title."""
    if sys.platform != "win32":
        return []
    else:
        import win32gui
        import win32process

        found: list[WindowInfo] = []

        def visit(hwnd: int, _: object) -> None:
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            found.append(WindowInfo(hwnd=hwnd, pid=pid, title=title))

        win32gui.EnumWindows(visit, None)
        return found


def _post_close(hwnd: int) -> None:
    if sys.platform == "win32":
        import win32con
        import win32gui

        with contextlib.suppress(Exception):  # the window may already be gone
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
