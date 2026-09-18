"""Risk score and verdict for one app, from its findings.

The whole policy is three small tables so it can be read, tuned and defended
in one screen:

* ``SEVERITY_WEIGHTS``: what one finding of each severity is worth.
* ``FAIL_THRESHOLD`` / ``WARN_THRESHOLD``: where the verdict flips.
* Each rule counts **once per app** at its highest severity. Twenty missing
  DLLs are one problem, not twenty; that is what keeps a noisy signal from
  drowning a real one. The score is capped at 100.
"""

from __future__ import annotations

from collections.abc import Iterable

from compatsentinel.models import Finding, Severity, Verdict

SEVERITY_WEIGHTS: dict[Severity, int] = {
    Severity.CRITICAL: 100,
    Severity.HIGH: 50,
    Severity.MEDIUM: 20,
    Severity.INFO: 0,
}

FAIL_THRESHOLD = 50
"""One high finding, or two mediums plus something, fails the app."""
WARN_THRESHOLD = 20
"""One medium finding is worth a look."""

SEVERITY_ORDER: tuple[Severity, ...] = (
    Severity.INFO,
    Severity.MEDIUM,
    Severity.HIGH,
    Severity.CRITICAL,
)
VERDICT_ORDER: tuple[Verdict, ...] = (Verdict.PASS, Verdict.WARN, Verdict.FAIL)


def severity_rank(severity: Severity) -> int:
    return SEVERITY_ORDER.index(severity)


def score_findings(findings: Iterable[Finding]) -> int:
    """Weighted sum over rules, each at its worst severity, capped at 100."""
    worst_per_rule: dict[str, Severity] = {}
    for finding in findings:
        current = worst_per_rule.get(finding.rule_id)
        if current is None or severity_rank(finding.severity) > severity_rank(current):
            worst_per_rule[finding.rule_id] = finding.severity
    total = sum(SEVERITY_WEIGHTS[severity] for severity in worst_per_rule.values())
    return min(total, 100)


def verdict_for(score: int) -> Verdict:
    if score >= FAIL_THRESHOLD:
        return Verdict.FAIL
    if score >= WARN_THRESHOLD:
        return Verdict.WARN
    return Verdict.PASS


def worst_verdict(verdicts: Iterable[Verdict]) -> Verdict:
    """The most severe verdict, or PASS when there are none."""
    return max(verdicts, key=VERDICT_ORDER.index, default=Verdict.PASS)


def sort_findings(findings: Iterable[Finding]) -> list[Finding]:
    """Most severe first; ties broken by rule id, then app id, then message.

    The engine emits findings in rule order; reports and the MCP server want
    the worst news on top. Sorting must be stable and deterministic so two runs
    over the same snapshots render identically.
    """
    return list(findings)  # TODO(juan): implement; see tests/test_scoring.py
