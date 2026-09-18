"""Single-file HTML report for a :class:`DiffResult`.

One file, inline CSS, no JavaScript frameworks, no external requests: the
report must open from a ticket attachment or a file share on a machine with
no internet, and it must not phone home. Light and dark mode follow the OS
preference through ``prefers-color-scheme``.

The full diff result is embedded as JSON in a ``<script type="application/json">``
block so the report stays machine readable: another tool (or the MCP server)
can recover exactly what the reader sees.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup

from compatsentinel import __version__
from compatsentinel.diff.rules import RULES_BY_ID
from compatsentinel.models import AppDiff, DiffResult, Finding, Severity, Verdict

SEVERITIES = (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.INFO)
VERDICTS = (Verdict.FAIL, Verdict.WARN, Verdict.PASS)


def render_html(
    result: DiffResult,
    *,
    generated_at: datetime | None = None,
    tool_version: str = __version__,
) -> str:
    """Render the report. Pure apart from the optional timestamp the caller passes in."""
    template = _environment().get_template("report.html.j2")
    return template.render(
        result=result,
        apps=result.apps,
        rules=[RULES_BY_ID[rule_id] for rule_id in sorted(_rule_ids_used(result))],
        severity_counts=severity_counts(f for app in result.apps for f in app.findings),
        verdict_counts=verdict_counts(result.apps),
        compared=sum(1 for app in result.apps if app.compared),
        generated_at=generated_at,
        tool_version=tool_version,
        data_json=embed_json(result),
    )


def write_report(result: DiffResult, path: Path, *, generated_at: datetime | None = None) -> Path:
    """Render and write the report atomically (temp file, then rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(render_html(result, generated_at=generated_at), encoding="utf-8")
    tmp.replace(path)
    return path


# --- Pure helpers (unit tested) ------------------------------------------------------------


def severity_counts(findings: Iterable[Finding]) -> dict[Severity, int]:
    counts = Counter(f.severity for f in findings)
    return {severity: counts.get(severity, 0) for severity in SEVERITIES}


def verdict_counts(apps: Iterable[AppDiff]) -> dict[Verdict, int]:
    counts = Counter(app.verdict for app in apps if app.compared)
    return {verdict: counts.get(verdict, 0) for verdict in VERDICTS}


def embed_json(result: DiffResult) -> Markup:
    """JSON safe to place inside a ``<script>`` element.

    Autoescaping must be bypassed (JSON is not HTML), so the one sequence that
    could terminate the element early, ``</``, is escaped by hand.
    """
    return Markup(result.model_dump_json().replace("</", "<\\/"))


def format_ms(value: float | None) -> str:
    return f"{value:.0f} ms" if value is not None else "-"


def format_delta(before_ms: float | None, after_ms: float | None) -> str:
    """Human delta between two startup times, e.g. ``+371 ms (+112%)``.

    Rules: empty string when either value is missing or ``before_ms`` is not
    positive; a leading sign always (``+`` or ``-``); the percentage relative to
    ``before_ms`` rounded to a whole number; ``no change`` when the difference
    rounds to 0 ms.
    """
    return ""  # TODO(juan): implement; see tests/test_html.py


def _rule_ids_used(result: DiffResult) -> set[str]:
    used = {f.rule_id for app in result.apps for f in app.findings}
    used.update(f.rule_id for f in result.environment_findings)
    return used


def _environment() -> Environment:
    env = Environment(
        loader=PackageLoader("compatsentinel.report", "templates"),
        autoescape=select_autoescape(default=True),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["ms"] = format_ms
    env.filters["delta"] = format_delta
    return env
