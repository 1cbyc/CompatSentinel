"""Environment fingerprint: pure parsers on any OS, full collection smoke."""

from __future__ import annotations

from compatsentinel import environment
from compatsentinel.models import Environment

HOTFIX_OUTPUT = """
KB5044284
KB5043080

KB5039895
KB5044284
"""

DOTNET_OUTPUT = """
Microsoft.AspNetCore.App 8.0.10 [C:\\Program Files\\dotnet\\shared\\Microsoft.AspNetCore.App]
Microsoft.NETCore.App 8.0.10 [C:\\Program Files\\dotnet\\shared\\Microsoft.NETCore.App]
Microsoft.NETCore.App 6.0.33 [C:\\Program Files\\dotnet\\shared\\Microsoft.NETCore.App]
garbage line without brackets
"""


def test_windows_11_is_detected_by_build() -> None:
    assert environment.windows_product_name(19045) == "Windows 10"
    assert environment.windows_product_name(22000) == "Windows 11"
    assert environment.windows_product_name(26100) == "Windows 11"
    assert environment.windows_product_name(None) == "Windows"


def test_hotfixes_are_unique_and_sorted_numerically() -> None:
    assert environment.parse_hotfix_output(HOTFIX_OUTPUT) == [
        "KB5039895",
        "KB5043080",
        "KB5044284",
    ]
    assert environment.parse_hotfix_output("") == []


def test_dotnet_runtimes_are_parsed() -> None:
    assert environment.parse_dotnet_runtimes(DOTNET_OUTPUT) == [
        "Microsoft.AspNetCore.App 8.0.10",
        "Microsoft.NETCore.App 6.0.33",
        "Microsoft.NETCore.App 8.0.10",
    ]


def test_collect_runs_on_any_os() -> None:
    env = environment.collect()
    assert isinstance(env, Environment)
    assert env.os_name
    assert env.python_version
