"""Compare two snapshots. Pure and deterministic: no I/O, no clock, no OS calls.

Given the same two :class:`Snapshot` objects and the same :class:`DiffConfig`,
``diff_snapshots`` always returns an identical :class:`DiffResult`. That is
what makes the diff testable on any OS from recorded JSON and safe to expose
through the MCP server.
"""

from __future__ import annotations

from collections.abc import Iterable

from compatsentinel.diff import scoring
from compatsentinel.diff.rules import RULES, RuleContext, environment_findings
from compatsentinel.models import AppDiff, AppRun, DiffConfig, DiffResult, Snapshot, Verdict

SIGNAL_FIELDS = ("launch", "modules", "events", "wer")


def diff_snapshots(
    before: Snapshot,
    after: Snapshot,
    config: DiffConfig | None = None,
    app_ids: Iterable[str] | None = None,
) -> DiffResult:
    """Diff every app present in either snapshot (or only ``app_ids``)."""
    config = config or DiffConfig()
    env_findings = environment_findings(before.environment, after.environment)
    ctx = RuleContext(config=config, environment_changed=bool(env_findings))

    wanted = set(app_ids) if app_ids is not None else None
    ordered = _ordered_app_ids(before, after)
    apps = [
        diff_app(before.app(app_id), after.app(app_id), app_id, ctx)
        for app_id in ordered
        if wanted is None or app_id in wanted
    ]
    return DiffResult(
        before_label=before.label,
        after_label=after.label,
        before_environment=before.environment,
        after_environment=after.environment,
        config=config,
        environment_findings=env_findings,
        apps=apps,
        verdict=scoring.worst_verdict(app.verdict for app in apps),
    )


def diff_app(before: AppRun | None, after: AppRun | None, app_id: str, ctx: RuleContext) -> AppDiff:
    """Run every rule for one app, then score it."""
    if before is None or after is None:
        side = "before" if before is None else "after"
        return AppDiff(
            app_id=app_id,
            compared=False,
            note=f"not present in the {side!s} snapshot",
            score=0,
            verdict=Verdict.PASS,
            before_outcome=before.launch.outcome if before and before.launch else None,
            after_outcome=after.launch.outcome if after and after.launch else None,
        )

    findings = [finding for rule in RULES for finding in rule.check(before, after, ctx)]
    findings = scoring.sort_findings(findings)
    score = scoring.score_findings(findings)
    return AppDiff(
        app_id=app_id,
        score=score,
        verdict=scoring.verdict_for(score),
        findings=findings,
        unavailable_signals=[
            name
            for name in SIGNAL_FIELDS
            if getattr(before, name) is None or getattr(after, name) is None
        ],
        before_outcome=before.launch.outcome if before.launch else None,
        after_outcome=after.launch.outcome if after.launch else None,
        before_startup_ms=before.launch.startup_ms if before.launch else None,
        after_startup_ms=after.launch.startup_ms if after.launch else None,
    )


def _ordered_app_ids(before: Snapshot, after: Snapshot) -> list[str]:
    """Before's order first, then apps that only exist in after."""
    seen: dict[str, None] = {}
    for run in (*before.apps, *after.apps):
        seen.setdefault(run.app_id, None)
    return list(seen)
