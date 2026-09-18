"""Module collector: path classification on any OS, live collection on self."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from compatsentinel.collectors.base import CollectorSkipped, RunContext
from compatsentinel.collectors.modules import (
    ModulesCollector,
    format_version,
    is_system_path,
    looks_like_module,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def ctx(*pids: int) -> RunContext:
    return RunContext(
        app_id="self", started_at=NOW, finished_at=NOW, pids=pids, image_names=frozenset()
    )


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (r"C:\Windows\System32\ntdll.dll", True),
        (r"c:\windows\system32\NTDLL.DLL", True),
        (r"C:\Windows\WinSxS\amd64_x\comctl32.dll", True),
        (r"C:\Program Files\Contoso\app.dll", False),
        (r"C:\WindowsApps\x.dll", False),
        (r"D:\Windows\System32\x.dll", False),
    ],
)
def test_is_system_path(path: str, expected: bool) -> None:
    assert is_system_path(path, r"C:\Windows") is expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (r"C:\Windows\System32\ntdll.dll", True),
        (r"C:\Program Files\App\App.EXE", True),
        ("/usr/lib/x86_64-linux-gnu/libc.so.6", True),
        ("/opt/python/lib/libpython3.11.so.1.0", True),
        ("/opt/python/lib/_pydantic_core.cpython-311-x86_64-linux-gnu.so", True),
        ("/usr/lib/libSystem.dylib", True),
        (r"C:\Windows\Fonts\segoeui.ttf", False),
        ("/usr/share/locale/locale-archive", False),
        ("/dev/shm/something.sock", False),
    ],
)
def test_looks_like_module(path: str, expected: bool) -> None:
    assert looks_like_module(path) is expected


def test_collects_modules_of_this_process() -> None:
    modules = ModulesCollector().collect(ctx(os.getpid()))
    assert modules, "the interpreter must have at least one mapped module"
    assert modules == sorted(modules, key=lambda m: m.path.lower())
    assert all(m.name and m.path for m in modules)


def test_skipped_when_no_process_is_alive() -> None:
    with pytest.raises(CollectorSkipped):
        ModulesCollector().collect(ctx(2**22 + 12345))


# --- Juan's Phase 2 task ------------------------------------------------------------
# Spec: format_version(most, least) -> str
#   * most packs major (high 16 bits) and minor (low 16 bits); least packs
#     build and revision the same way.
#   * Inputs may be negative because pywin32 returns signed 32-bit ints. Mask
#     each DWORD with 0xFFFFFFFF first, then split with >> 16 and & 0xFFFF.
#   * Return "major.minor.build.revision" (change the return annotation to str).
# Until this is done file_version() returns None and snapshots have no DLL
# versions, so the MODULE_VERSION_CHANGED rule cannot fire. Remove the skips
# when done.


@pytest.mark.skip(reason="TODO(juan): implement format_version")
def test_format_version_plain() -> None:
    assert format_version(0x000A0000, 0x66040E1F) == "10.0.26116.3615"


@pytest.mark.skip(reason="TODO(juan): implement format_version")
def test_format_version_handles_signed_input() -> None:
    # 0x83C20000 as a signed 32-bit int is negative; build must still be 33730.
    assert format_version(0x000E0028, 0x83C20000 - 2**32) == "14.40.33730.0"
