"""CLI surface tests: these run on every OS."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from compatsentinel import __version__
from compatsentinel.cli import app


def test_help_lists_doctor(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "doctor" in result.output


def test_no_args_shows_help(runner: CliRunner) -> None:
    result = runner.invoke(app, [])
    # Typer exits 0 for --help but 2 when help is shown because no args were given.
    assert result.exit_code in (0, 2)
    assert "Usage" in result.output


def test_version_flag(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_doctor_runs_anywhere(runner: CliRunner) -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Python" in result.output
    assert "pywin32" in result.output


def test_validate_example_suite(runner: CliRunner) -> None:
    result = runner.invoke(app, ["validate", "examples/apps.yaml"])
    assert result.exit_code == 0, result.output
    assert "notepad" in result.output
    assert "Suite is valid" in result.output


def test_validate_reports_errors_and_exits_1(runner: CliRunner, tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("apps:\n  - id: notepad\n", encoding="utf-8")
    result = runner.invoke(app, ["validate", str(bad)])
    assert result.exit_code == 1
    assert "apps.0.command" in result.output
