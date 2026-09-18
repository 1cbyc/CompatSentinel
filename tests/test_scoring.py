"""Scoring policy: weights, once-per-rule, cap, thresholds."""

from __future__ import annotations

import pytest

from compatsentinel.diff import scoring
from compatsentinel.models import Finding, Severity, Verdict


def finding(rule_id: str, severity: Severity, app_id: str = "a", message: str = "m") -> Finding:
    return Finding(rule_id=rule_id, severity=severity, app_id=app_id, message=message)


def test_no_findings_is_a_clean_pass() -> None:
    assert scoring.score_findings([]) == 0
    assert scoring.verdict_for(0) is Verdict.PASS


def test_each_severity_has_the_documented_weight() -> None:
    assert scoring.score_findings([finding("X", Severity.INFO)]) == 0
    assert scoring.score_findings([finding("X", Severity.MEDIUM)]) == 20
    assert scoring.score_findings([finding("X", Severity.HIGH)]) == 50
    assert scoring.score_findings([finding("X", Severity.CRITICAL)]) == 100


def test_a_rule_counts_once_at_its_worst_severity() -> None:
    twenty_missing = [finding("MODULE_MISSING", Severity.MEDIUM, message=str(i)) for i in range(20)]
    assert scoring.score_findings(twenty_missing) == 20
    mixed = [
        finding("R", Severity.INFO),
        finding("R", Severity.HIGH),
        finding("R", Severity.MEDIUM),
    ]
    assert scoring.score_findings(mixed) == 50


def test_different_rules_add_up_and_cap_at_100() -> None:
    assert (
        scoring.score_findings([finding("A", Severity.MEDIUM), finding("B", Severity.MEDIUM)]) == 40
    )
    assert scoring.score_findings([finding("A", Severity.HIGH), finding("B", Severity.HIGH)]) == 100
    assert (
        scoring.score_findings([finding("A", Severity.CRITICAL), finding("B", Severity.HIGH)])
        == 100
    )


@pytest.mark.parametrize(
    ("score", "verdict"),
    [
        (0, Verdict.PASS),
        (19, Verdict.PASS),
        (20, Verdict.WARN),
        (49, Verdict.WARN),
        (50, Verdict.FAIL),
        (100, Verdict.FAIL),
    ],
)
def test_verdict_thresholds(score: int, verdict: Verdict) -> None:
    assert scoring.verdict_for(score) is verdict


def test_worst_verdict() -> None:
    assert scoring.worst_verdict([]) is Verdict.PASS
    assert scoring.worst_verdict([Verdict.PASS, Verdict.WARN, Verdict.PASS]) is Verdict.WARN
    assert scoring.worst_verdict([Verdict.WARN, Verdict.FAIL]) is Verdict.FAIL


# --- Juan's Phase 3 task (b) ---------------------------------------------------------
# Spec: sort_findings(findings) -> list[Finding]
#   * Most severe first (use severity_rank), then rule_id ascending, then
#     app_id ascending (None sorts first), then message ascending.
#   * Return a new list; do not mutate the input. sorted() with a key tuple is
#     the idiomatic one-liner; remember to negate the rank for descending order.
# Remove the skip when done.


@pytest.mark.skip(reason="TODO(juan): implement sort_findings")
def test_sort_findings_orders_by_severity_then_rule_then_app() -> None:
    unsorted = [
        finding("MODULE_MISSING", Severity.MEDIUM, app_id="b"),
        finding("ENV_CHANGED", Severity.INFO, app_id=None),  # type: ignore[arg-type]
        finding("LAUNCH_FAILED", Severity.CRITICAL, app_id="z"),
        finding("MODULE_MISSING", Severity.MEDIUM, app_id="a", message="zzz"),
        finding("MODULE_MISSING", Severity.MEDIUM, app_id="a", message="aaa"),
        finding("EXIT_CODE_CHANGED", Severity.HIGH, app_id="a"),
    ]
    result = scoring.sort_findings(unsorted)
    assert [(f.rule_id, f.app_id, f.message) for f in result] == [
        ("LAUNCH_FAILED", "z", "m"),
        ("EXIT_CODE_CHANGED", "a", "m"),
        ("MODULE_MISSING", "a", "aaa"),
        ("MODULE_MISSING", "a", "zzz"),
        ("MODULE_MISSING", "b", "m"),
        ("ENV_CHANGED", None, "m"),
    ]
    assert unsorted[0].rule_id == "MODULE_MISSING"  # input untouched
