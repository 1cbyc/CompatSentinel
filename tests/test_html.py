"""HTML report: offline, escaped, self-describing, readable in both colour schemes."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from compatsentinel.diff import diff_snapshots
from compatsentinel.models import DiffResult, Severity, Verdict
from compatsentinel.report import html
from compatsentinel.store import SnapshotStore
from tests.factories import make_event, make_run, make_snapshot

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "snapshots"


@pytest.fixture(scope="module")
def demo() -> DiffResult:
    store = SnapshotStore(EXAMPLES)
    return diff_snapshots(store.load(EXAMPLES / "before"), store.load(EXAMPLES / "after"))


@pytest.fixture(scope="module")
def page(demo: DiffResult) -> str:
    return html.render_html(demo, generated_at=datetime(2026, 9, 18, 12, 0, tzinfo=UTC))


def test_page_is_a_complete_html_document(page: str) -> None:
    assert page.lstrip().lower().startswith("<!doctype html>")
    assert "</html>" in page
    assert "<title>CompatSentinel: before vs after (FAIL)</title>" in page
    assert "generated 2026-09-18 12:00 UTC" in page


def test_page_makes_no_external_requests(page: str) -> None:
    assert "<link" not in page
    assert "<script src" not in page
    assert "@import" not in page
    assert "url(" not in page
    assert not re.search(r"""(src|href)=["']https?://""", page)
    assert "<style>" in page  # everything inline


def test_page_supports_light_and_dark(page: str) -> None:
    assert "prefers-color-scheme: dark" in page
    assert '<meta name="color-scheme" content="light dark">' in page


def test_page_shows_every_app_and_rule(page: str, demo: DiffResult) -> None:
    for app in demo.apps:
        assert f'id="app-{app.app_id}"' in page
    for rule_id in ("LAUNCH_FAILED", "CRASH_NEW", "STARTUP_REGRESSION", "MODULE_MISSING"):
        assert rule_id in page
    assert "informational finding(s)" in page  # info findings are collapsed
    assert "not compared: modules" in page


def test_embedded_json_round_trips(page: str, demo: DiffResult) -> None:
    match = re.search(
        r'<script type="application/json" id="compatsentinel-diff">(.*?)</script>', page, re.S
    )
    assert match
    assert DiffResult.model_validate_json(match.group(1)) == demo


def test_html_is_escaped_including_inside_the_json_block() -> None:
    evil = "</script><script>alert('x')</script>"
    before = make_snapshot(apps=[make_run("evil<b>app")])
    after = make_snapshot(apps=[make_run("evil<b>app", events=[make_event(message=evil)])])
    page = html.render_html(diff_snapshots(before, after))
    markup, _, data = page.partition('<script type="application/json"')
    assert "<b>app" not in markup and "evil&lt;b&gt;app" in markup
    assert "<script>alert" not in markup
    # Inside the JSON block only "</" is dangerous; it must be broken up.
    assert "</script>" not in data.split("</script>")[0]
    # The JSON block still parses and carries the original text.
    blob = re.search(r'id="compatsentinel-diff">(.*?)</script>', page, re.S)
    assert blob and json.loads(blob.group(1))["apps"][0]["findings"][0]["message"].endswith(evil)


def test_counts_helpers(demo: DiffResult) -> None:
    sev = html.severity_counts(f for app in demo.apps for f in app.findings)
    assert sev[Severity.CRITICAL] == 4 and sev[Severity.HIGH] == 2 and sev[Severity.MEDIUM] == 2
    assert html.verdict_counts(demo.apps) == {Verdict.FAIL: 2, Verdict.WARN: 2, Verdict.PASS: 0}
    assert html.format_ms(331.9) == "332 ms" and html.format_ms(None) == "-"


def test_write_report_is_atomic(tmp_path: Path, demo: DiffResult) -> None:
    out = html.write_report(demo, tmp_path / "nested" / "report.html")
    assert out.is_file() and out.stat().st_size > 10_000
    assert not out.with_suffix(".html.tmp").exists()


# --- Juan's Phase 4 task ------------------------------------------------------------------
# Spec: format_delta(before_ms, after_ms) -> str   (report/html.py)
#   * "" when either value is None or before_ms <= 0.
#   * Otherwise "+371 ms (+112%)" / "-50 ms (-12%)" with whole numbers.
#   * "no change" when the difference rounds to 0 ms.
# The template already calls it: once implemented, the Apps table shows the
# delta under each startup pair. Remove the skip when done.


@pytest.mark.skip(reason="TODO(juan): implement format_delta")
def test_format_delta() -> None:
    assert html.format_delta(331.9, 702.5) == "+371 ms (+112%)"
    assert html.format_delta(400.0, 350.0) == "-50 ms (-12%)"
    assert html.format_delta(400.0, 400.3) == "no change"
    assert html.format_delta(None, 400.0) == ""
    assert html.format_delta(0.0, 400.0) == ""
