"""CLI surface tests: these run on every OS."""

from __future__ import annotations

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
