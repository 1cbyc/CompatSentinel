"""MCP server tests: an in-process client talking to the server over memory streams.

No subprocess, no stdio framing — ``create_connected_server_and_client_session``
wires a real :class:`mcp.ClientSession` to the server's request handlers
directly, so these tests exercise the same code path a real MCP client uses.

Each test opens its own client session inside a single ``async with`` rather
than through a fixture: the session's internal task group must be entered and
exited in the same asyncio task, which an async-generator fixture (setup
before the test's task, teardown after it) does not guarantee.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from mcp import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session

from compatsentinel.mcp_server import build_server

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "snapshots"


@asynccontextmanager
async def session_for(store_dir: Path) -> AsyncIterator[ClientSession]:
    server = build_server(store_dir)
    async with create_connected_server_and_client_session(server._mcp_server) as client:
        yield client


# --- Server metadata and safety ------------------------------------------------------


async def test_server_exposes_exactly_the_documented_tools() -> None:
    async with session_for(EXAMPLES) as client:
        result = await client.list_tools()
    assert {t.name for t in result.tools} == {
        "list_snapshots",
        "get_environment",
        "get_app_run",
        "diff",
        "explain_finding",
    }


def test_server_never_imports_the_runner() -> None:
    """The module that can launch and close apps must not be reachable from here."""
    import compatsentinel.mcp_server as mod

    assert "runner" not in vars(mod)
    assert "compatsentinel.runner" not in {
        getattr(v, "__module__", None) for v in vars(mod).values()
    }


async def test_resource_template_is_the_snapshot() -> None:
    async with session_for(EXAMPLES) as client:
        result = await client.list_resource_templates()
    assert [t.uriTemplate for t in result.resourceTemplates] == ["snapshot://{label}"]
    assert result.resourceTemplates[0].mimeType == "application/json"


# --- list_snapshots -------------------------------------------------------------------


async def test_list_snapshots() -> None:
    async with session_for(EXAMPLES) as client:
        result = await client.call_tool("list_snapshots", {})
    assert result.isError is False
    assert result.structuredContent == {"result": ["after", "before"]}


async def test_list_snapshots_empty_store(tmp_path: Path) -> None:
    async with session_for(tmp_path / "snapshots") as client:
        result = await client.call_tool("list_snapshots", {})
    assert result.structuredContent == {"result": []}


# --- get_environment -----------------------------------------------------------------


async def test_get_environment() -> None:
    async with session_for(EXAMPLES) as client:
        result = await client.call_tool("get_environment", {"label": "after"})
    assert result.isError is False
    data = result.structuredContent
    assert data is not None
    assert data["display_version"] == "24H2"
    assert data["build"] == 26100


async def test_get_environment_unknown_label_is_a_tool_error() -> None:
    async with session_for(EXAMPLES) as client:
        result = await client.call_tool("get_environment", {"label": "does-not-exist"})
    assert result.isError is True
    assert "not found" in result.content[0].text  # type: ignore[union-attr]


# --- get_app_run ----------------------------------------------------------------------


async def test_get_app_run() -> None:
    async with session_for(EXAMPLES) as client:
        result = await client.call_tool(
            "get_app_run", {"label": "after", "app_id": "contoso-ledger"}
        )
    assert result.isError is False
    data = result.structuredContent
    assert data is not None
    assert data["launch"]["outcome"] == "exited"
    assert len(data["wer"]) == 1


async def test_get_app_run_unknown_app_lists_what_is_available() -> None:
    async with session_for(EXAMPLES) as client:
        result = await client.call_tool("get_app_run", {"label": "before", "app_id": "nope"})
    assert result.isError is True
    message = result.content[0].text  # type: ignore[union-attr]
    assert "nope" in message
    assert "notepad" in message  # the error names the real app ids


# --- diff -------------------------------------------------------------------------------


async def test_diff_whole_suite() -> None:
    async with session_for(EXAMPLES) as client:
        result = await client.call_tool("diff", {"before": "before", "after": "after"})
    assert result.isError is False
    data = result.structuredContent
    assert data is not None
    assert data["verdict"] == "fail"
    assert {app["app_id"] for app in data["apps"]} == {
        "notepad",
        "calculator",
        "contoso-ledger",
        "wordpad-legacy",
    }


async def test_diff_single_app() -> None:
    async with session_for(EXAMPLES) as client:
        result = await client.call_tool(
            "diff", {"before": "before", "after": "after", "app_id": "contoso-ledger"}
        )
    data = result.structuredContent
    assert data is not None
    assert [app["app_id"] for app in data["apps"]] == ["contoso-ledger"]
    assert data["verdict"] == "fail"


async def test_diff_missing_snapshot_is_a_tool_error() -> None:
    async with session_for(EXAMPLES) as client:
        result = await client.call_tool("diff", {"before": "nope", "after": "after"})
    assert result.isError is True


# --- explain_finding --------------------------------------------------------------------


async def test_explain_finding() -> None:
    async with session_for(EXAMPLES) as client:
        result = await client.call_tool("explain_finding", {"rule_id": "LAUNCH_FAILED"})
    assert result.isError is False
    assert result.structuredContent == {
        "rule_id": "LAUNCH_FAILED",
        "severity": "critical",
        "summary": "App launched before, fails or times out after.",
    }


async def test_explain_finding_covers_every_rule_used_by_the_engine() -> None:
    from compatsentinel.diff.rules import RULES, RULES_BY_ID

    async with session_for(EXAMPLES) as client:
        for rule in (*RULES, RULES_BY_ID["ENV_CHANGED"]):
            result = await client.call_tool("explain_finding", {"rule_id": rule.id})
            assert result.isError is False, rule.id


async def test_explain_finding_unknown_rule_lists_known_ones() -> None:
    async with session_for(EXAMPLES) as client:
        result = await client.call_tool("explain_finding", {"rule_id": "NOT_A_RULE"})
    assert result.isError is True
    message = result.content[0].text  # type: ignore[union-attr]
    assert "CRASH_NEW" in message


# --- snapshot resource ------------------------------------------------------------------


async def test_read_snapshot_resource() -> None:
    async with session_for(EXAMPLES) as client:
        result = await client.read_resource("snapshot://before")  # type: ignore[arg-type]
    assert len(result.contents) == 1
    content = result.contents[0]
    assert content.mimeType == "application/json"
    assert '"label": "before"' in content.text  # type: ignore[union-attr]


async def test_read_snapshot_resource_unknown_label_raises() -> None:
    async with session_for(EXAMPLES) as client:
        with pytest.raises(Exception, match="not found"):
            await client.read_resource("snapshot://does-not-exist")  # type: ignore[arg-type]
