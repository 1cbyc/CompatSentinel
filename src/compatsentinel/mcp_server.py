"""Read-only MCP server over stored snapshots.

Exposes captured data to an AI assistant so it can answer questions like
"what changed for app X between these two snapshots, and which findings
matter?" without the assistant ever touching the machine under test.

Security posture, mirroring IntuneGraph: **the assistant reads exported data
and nothing else.** This module never imports :mod:`compatsentinel.runner`
or any collector, so there is no code path from an MCP tool call to launching,
closing or otherwise touching a process. Every tool is a pure read against
:class:`~compatsentinel.store.SnapshotStore` or the pure diff engine. No tool
takes a file path outside the configured snapshot store, makes a network
call, or writes anything to disk.

Errors (an unknown label, app id or rule id) are raised as :class:`ValueError`
and turned into a tool error result by the MCP framework; the process itself
never crashes on bad input.
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from compatsentinel import __version__
from compatsentinel.diff import diff_snapshots
from compatsentinel.diff.rules import RULES_BY_ID
from compatsentinel.models import AppRun, DiffResult, Environment, Snapshot
from compatsentinel.store import SnapshotStore, StoreError

INSTRUCTIONS = """
CompatSentinel exposes read-only access to stored capture snapshots, each a
behavioural fingerprint of a set of Windows applications taken before or
after a change (a Windows update, a new build, a machine reconfiguration).

Typical workflow: call list_snapshots to see what is available, then diff
two labels to get a scored list of findings, then use get_app_run or
get_environment to pull the detail behind a specific finding, and
explain_finding to look up what a rule id means. Nothing here launches an
application or modifies the host: nothing can.
""".strip()


def build_server(store_dir: Path | str = Path("snapshots")) -> FastMCP:
    """Construct the server bound to snapshots under ``store_dir``.

    A fresh :class:`FastMCP` is built per call (rather than at import time)
    so tests and the CLI can point the server at different snapshot stores,
    e.g. ``examples/snapshots`` for a demo run.
    """
    store = SnapshotStore(Path(store_dir))
    server = FastMCP(
        "compatsentinel",
        instructions=INSTRUCTIONS,
        website_url="https://github.com/juandresrodca/CompatSentinel",
    )

    @server.tool()
    def list_snapshots() -> list[str]:
        """List the labels of every stored snapshot, alphabetically."""
        return store.list_labels()

    @server.tool()
    def get_environment(label: str) -> Environment:
        """OS fingerprint (build, UBR, edition, hotfixes, runtimes) for one snapshot."""
        return _load(store, label).environment

    @server.tool()
    def get_app_run(label: str, app_id: str) -> AppRun:
        """Everything captured for one app in one snapshot: launch, modules, events, WER."""
        snapshot = _load(store, label)
        run = snapshot.app(app_id)
        if run is None:
            available = ", ".join(sorted(a.app_id for a in snapshot.apps)) or "(none)"
            raise ValueError(f"no app {app_id!r} in snapshot {label!r}; available: {available}")
        return run

    @server.tool()
    def diff(before: str, after: str, app_id: str | None = None) -> DiffResult:
        """Compare two snapshots and return findings, scores and verdicts.

        Pass ``app_id`` to restrict the comparison to one app; omit it to
        diff every app present in either snapshot.
        """
        before_snapshot = _load(store, before)
        after_snapshot = _load(store, after)
        app_ids = [app_id] if app_id is not None else None
        return diff_snapshots(before_snapshot, after_snapshot, app_ids=app_ids)

    @server.tool()
    def explain_finding(rule_id: str) -> dict[str, str]:
        """Look up a diff rule by id: its default severity and what it detects."""
        rule = RULES_BY_ID.get(rule_id)
        if rule is None:
            available = ", ".join(sorted(RULES_BY_ID))
            raise ValueError(f"unknown rule id {rule_id!r}; known rules: {available}")
        return {"rule_id": rule.id, "severity": rule.severity.value, "summary": rule.summary}

    @server.resource(
        "snapshot://{label}",
        name="snapshot",
        description="The raw snapshot JSON for one label.",
        mime_type="application/json",
    )
    def snapshot_resource(label: str) -> str:
        return _load(store, label).model_dump_json(indent=2)

    return server


def _load(store: SnapshotStore, label: str) -> Snapshot:
    """Load a snapshot or raise a ValueError an MCP client can display."""
    try:
        return store.load(label)
    except StoreError as exc:
        raise ValueError(str(exc)) from exc


def run(store_dir: Path | str = Path("snapshots")) -> None:
    """Run the server on stdio. This is what ``compatsentinel mcp`` calls."""
    build_server(store_dir).run(transport="stdio")


__all__ = ["__version__", "build_server", "run"]
