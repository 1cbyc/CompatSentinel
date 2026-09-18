"""Command line entry point (``compatsentinel``).

Commands are added phase by phase. Keep this module thin: parse arguments,
call into the library, render the result. No business logic lives here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from compatsentinel import __version__, doctor, suite

app = typer.Typer(
    name="compatsentinel",
    help="Catch Windows app compatibility regressions before your users do.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"compatsentinel {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show the version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Capture behavioural fingerprints of Windows apps and diff them across updates."""


@app.command("doctor")
def doctor_command() -> None:
    """Check Python, OS and optional Windows dependencies."""
    report = doctor.collect()

    table = Table(title="CompatSentinel doctor", show_header=False)
    table.add_column("Check", style="bold")
    table.add_column("Value")
    table.add_row("Python", report.python_version)
    table.add_row("Interpreter", report.python_executable)
    # platform.release() reports "10" on Windows 11, so show the build instead.
    table.add_row("OS", f"{report.os_name} {report.os_version}")
    table.add_row("Machine", report.machine)
    table.add_row("pywin32", _yes_no(report.pywin32_available))
    table.add_row("Capture supported", _yes_no(report.capture_supported))
    console.print(table)

    if not report.capture_supported:
        console.print(
            "[yellow]Capture needs Windows 10/11. diff, report and mcp work on any OS.[/yellow]"
        )


@app.command()
def validate(
    suite_path: Annotated[
        Path, typer.Argument(help="Path to the suite file (apps.yaml).", metavar="SUITE")
    ],
) -> None:
    """Validate a suite file and list the apps it would run."""
    try:
        loaded = suite.load_suite(suite_path)
    except suite.SuiteError as exc:
        # markup=False: validation messages may contain [brackets] rich would eat.
        console.print(str(exc), style="red", markup=False)
        raise typer.Exit(code=1) from None

    table = Table(title=f"{suite_path}: {len(loaded.apps)} app(s)")
    table.add_column("id", style="bold")
    table.add_column("command", overflow="fold")
    table.add_column("window regex")
    table.add_column("timeout", justify="right")
    table.add_column("repeats", justify="right")
    table.add_column("tags")
    for spec in loaded.apps:
        settings = spec.effective(loaded.defaults)
        table.add_row(
            spec.id,
            " ".join([spec.command, *spec.args]),
            spec.window_title_regex or "-",
            f"{settings.timeout_seconds}s",
            str(settings.repeats),
            ", ".join(spec.tags) or "-",
        )
    console.print(table)
    console.print("[green]Suite is valid.[/green]")


def _yes_no(value: bool) -> str:
    return "[green]yes[/green]" if value else "[red]no[/red]"
