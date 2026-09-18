"""Loaded modules (DLLs) of the app's live processes, via psutil memory maps.

Runs while the app is up. Works without elevation for processes owned by the
current user, including packaged (Store) apps; other users' processes raise
``AccessDenied`` and are reported as such.
"""

from __future__ import annotations

import os
import sys
from pathlib import PureWindowsPath

import psutil

from compatsentinel.collectors.base import CollectorSkipped, RunContext
from compatsentinel.models import ModuleInfo

MODULE_SUFFIXES = (".dll", ".exe", ".dylib")
"""Windows modules plus macOS libraries; Linux ``.so`` files are matched separately."""


def looks_like_module(path: str) -> bool:
    """True for DLLs, executables and Unix shared objects (``libc.so.6`` included).

    Unix libraries carry the version after ``.so``, so a plain suffix check is
    not enough; the collector must work on Linux so tests can run there.
    """
    name = PureWindowsPath(path).name.lower()
    return name.endswith(MODULE_SUFFIXES) or name.endswith(".so") or ".so." in name


class ModulesCollector:
    name = "modules"
    requires_elevation = False

    def collect(self, ctx: RunContext) -> list[ModuleInfo]:
        paths: set[str] = set()
        denied: list[int] = []
        inspected = 0
        for pid in ctx.pids:
            try:
                maps = psutil.Process(pid).memory_maps(grouped=True)
            except psutil.NoSuchProcess:
                continue
            except psutil.AccessDenied:
                denied.append(pid)
                continue
            inspected += 1
            paths.update(m.path for m in maps if looks_like_module(m.path))

        if inspected == 0:
            if denied:
                raise PermissionError(f"access denied to process(es) {denied}")
            raise CollectorSkipped("no live process to inspect")

        system_root = os.environ.get("SYSTEMROOT", r"C:\Windows")
        return [
            ModuleInfo(
                name=PureWindowsPath(path).name,
                path=path,
                version=file_version(path),
                is_system=is_system_path(path, system_root),
            )
            for path in sorted(paths, key=str.lower)
        ]


def is_system_path(path: str, system_root: str = r"C:\Windows") -> bool:
    """True when ``path`` lives under the Windows directory (case-insensitive)."""
    return PureWindowsPath(path).is_relative_to(PureWindowsPath(system_root))


def file_version(path: str) -> str | None:
    """File version from the PE version resource, or None when unavailable."""
    if sys.platform != "win32":
        return None
    else:
        import pywintypes
        import win32api

        try:
            info = win32api.GetFileVersionInfo(path, "\\")
        except pywintypes.error:
            return None
        return format_version(info["FileVersionMS"], info["FileVersionLS"])


def format_version(most: int, least: int) -> str | None:
    """Render ``FileVersionMS``/``FileVersionLS`` as ``major.minor.build.revision``.

    Each DWORD packs two 16-bit numbers: the high word of ``most`` is the major
    version, its low word the minor; ``least`` holds build and revision the
    same way. pywin32 hands them over as *signed* 32-bit ints, so a build
    number with the top bit set (33730 = 0x83C2) arrives as a negative
    ``least``. Mask before you shift, or you will print ``14.40.-31806.0``.
    """
    return None  # TODO(juan): implement; see tests/test_modules.py
