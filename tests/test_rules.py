"""One positive and one negative case per rule, plus the edge that motivated it."""

from __future__ import annotations

import pytest

from compatsentinel.diff import rules
from compatsentinel.diff.rules import RULES, RULES_BY_ID, RuleContext
from compatsentinel.models import DiffConfig, LaunchOutcome, ModuleInfo, Severity
from tests.factories import (
    APP_MODULES,
    SYSTEM_MODULES,
    make_environment,
    make_event,
    make_launch,
    make_run,
    make_wer,
)

CTX = RuleContext(config=DiffConfig(), environment_changed=False)
CTX_ENV_CHANGED = RuleContext(config=DiffConfig(), environment_changed=True)


def ids(findings: list[object]) -> list[str]:
    return [f.rule_id for f in findings]  # type: ignore[attr-defined]


# --- registry -----------------------------------------------------------------------


def test_registry_ids_are_unique_and_documented() -> None:
    rule_ids = [rule.id for rule in RULES]
    assert len(rule_ids) == len(set(rule_ids))
    for rule in RULES:
        assert rule.summary.endswith(".")
        assert RULES_BY_ID[rule.id] is rule
    assert "ENV_CHANGED" in RULES_BY_ID


def test_healthy_identical_runs_produce_no_findings() -> None:
    before, after = make_run(), make_run()
    assert [f for rule in RULES for f in rule.check(before, after, CTX)] == []


# --- LAUNCH_FAILED --------------------------------------------------------------------


@pytest.mark.parametrize(
    "outcome", [LaunchOutcome.TIMEOUT, LaunchOutcome.FAILED_TO_START, LaunchOutcome.EXITED]
)
def test_launch_failed_fires_when_ok_before_and_not_after(outcome: LaunchOutcome) -> None:
    after = make_run(
        launch=make_launch(outcome=outcome, startup_ms=None, exit_code=1, error="boom")
    )
    findings = rules.launch_failed(make_run(), after, CTX)
    assert ids(findings) == ["LAUNCH_FAILED"]
    assert findings[0].severity is Severity.CRITICAL
    assert findings[0].before == "ok" and findings[0].after == outcome.value
    assert "boom" in findings[0].message


def test_launch_failed_is_silent_when_it_was_already_broken() -> None:
    broken = make_run(launch=make_launch(outcome=LaunchOutcome.TIMEOUT, startup_ms=None))
    assert rules.launch_failed(broken, broken, CTX) == []


def test_launch_failed_needs_both_signals() -> None:
    no_launch = make_run(launch=None).model_copy(update={"launch": None})
    assert rules.launch_failed(make_run(), no_launch, CTX) == []


# --- CRASH_NEW -------------------------------------------------------------------------


def test_crash_new_from_wer_report() -> None:
    after = make_run(wer=[make_wer()])
    findings = rules.crash_new(make_run(), after, CTX)
    assert ids(findings) == ["CRASH_NEW"]
    assert findings[0].severity is Severity.CRITICAL
    assert "Contoso.Core.dll" in findings[0].message
    assert findings[0].before == "no crash evidence"


def test_crash_new_from_application_error_event() -> None:
    event = make_event(
        source="Application Error", event_id=1000, message="App.exe | 3.2.1.0 | KERNELBASE.dll"
    )
    findings = rules.crash_new(make_run(), make_run(events=[event]), CTX)
    assert ids(findings) == ["CRASH_NEW"]
    assert "Application Error 1000" in findings[0].message


def test_crash_new_ignores_crashes_that_already_happened_before() -> None:
    crashed = make_run(wer=[make_wer()])
    assert rules.crash_new(crashed, crashed, CTX) == []
    # A *different* crash after a known one is still new.
    other = make_run(wer=[make_wer(fault_module="ntdll.dll")])
    findings = rules.crash_new(crashed, other, CTX)
    assert len(findings) == 1 and findings[0].before == "1 crash(es) already present"


def test_crash_new_treats_missing_signals_as_no_evidence() -> None:
    assert rules.crash_new(make_run(no_wer=True, no_events=True), make_run(), CTX) == []


# --- EXIT_CODE_CHANGED -------------------------------------------------------------------


def test_exit_code_changed() -> None:
    after = make_run(launch=make_launch(exit_code=3))
    findings = rules.exit_code_changed(make_run(), after, CTX)
    assert ids(findings) == ["EXIT_CODE_CHANGED"]
    assert findings[0].severity is Severity.HIGH
    assert (findings[0].before, findings[0].after) == ("0", "3")


def test_exit_code_unknown_on_either_side_is_not_a_change() -> None:
    unknown = make_run(launch=make_launch(exit_code=None))
    assert rules.exit_code_changed(make_run(), unknown, CTX) == []
    assert rules.exit_code_changed(unknown, make_run(), CTX) == []


# --- STARTUP_REGRESSION ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("before_ms", "after_ms", "expected"),
    [
        (400.0, 800.0, True),  # +100%, +400 ms
        (400.0, 720.0, True),  # +80%, +320 ms: both thresholds met
        (400.0, 690.0, False),  # +72% but only +290 ms
        (2000.0, 2400.0, False),  # +400 ms but only +20%
        (400.0, 300.0, False),  # faster
    ],
)
def test_startup_regression_thresholds(before_ms: float, after_ms: float, expected: bool) -> None:
    before = make_run(launch=make_launch(startup_ms=before_ms))
    after = make_run(launch=make_launch(startup_ms=after_ms))
    findings = rules.startup_regression(before, after, CTX)
    assert bool(findings) is expected
    if expected:
        assert findings[0].severity is Severity.MEDIUM
        assert f"{before_ms:.0f} ms -> {after_ms:.0f} ms" in findings[0].message


def test_startup_regression_thresholds_are_configurable() -> None:
    ctx = RuleContext(DiffConfig(startup_regression_pct=5, startup_regression_ms=50), False)
    before = make_run(launch=make_launch(startup_ms=1000.0))
    after = make_run(launch=make_launch(startup_ms=1080.0))
    assert rules.startup_regression(before, after, CTX) == []
    assert ids(rules.startup_regression(before, after, ctx)) == ["STARTUP_REGRESSION"]


def test_startup_regression_needs_timings() -> None:
    untimed = make_run(launch=make_launch(startup_ms=None))
    assert rules.startup_regression(untimed, make_run(), CTX) == []


# --- MODULE_MISSING ------------------------------------------------------------------------


def test_module_missing() -> None:
    after = make_run(modules=SYSTEM_MODULES + APP_MODULES[:1])
    findings = rules.module_missing(make_run(), after, CTX)
    assert ids(findings) == ["MODULE_MISSING"]
    assert findings[0].severity is Severity.MEDIUM
    assert "Contoso.Core.dll" in findings[0].message
    assert findings[0].after == "not loaded"


def test_module_missing_matches_names_case_insensitively() -> None:
    renamed = [m.model_copy(update={"name": m.name.upper()}) for m in SYSTEM_MODULES + APP_MODULES]
    assert rules.module_missing(make_run(), make_run(modules=renamed), CTX) == []


def test_module_missing_is_silent_without_module_data() -> None:
    assert rules.module_missing(make_run(), make_run(no_modules=True), CTX) == []


# --- MODULE_VERSION_CHANGED --------------------------------------------------------------------


def bump(module: ModuleInfo, version: str) -> ModuleInfo:
    return module.model_copy(update={"version": version})


def test_app_dll_version_change_is_info() -> None:
    after = make_run(modules=[*SYSTEM_MODULES, bump(APP_MODULES[0], "3.3.0.0"), APP_MODULES[1]])
    findings = rules.module_version_changed(make_run(), after, CTX)
    assert ids(findings) == ["MODULE_VERSION_CHANGED"]
    assert findings[0].severity is Severity.INFO
    assert (findings[0].before, findings[0].after) == ("3.2.1.0", "3.3.0.0")


def test_system_dll_change_without_os_update_is_medium() -> None:
    after = make_run(
        modules=[bump(SYSTEM_MODULES[0], "10.0.26100.9999"), SYSTEM_MODULES[1], *APP_MODULES]
    )
    findings = rules.module_version_changed(make_run(), after, CTX)
    assert findings[0].severity is Severity.MEDIUM
    assert "without an OS update" in findings[0].message


def test_system_dll_change_with_os_update_is_expected_info() -> None:
    after = make_run(
        modules=[bump(SYSTEM_MODULES[0], "10.0.26100.9999"), SYSTEM_MODULES[1], *APP_MODULES]
    )
    findings = rules.module_version_changed(make_run(), after, CTX_ENV_CHANGED)
    assert findings[0].severity is Severity.INFO
    assert "expected after the OS update" in findings[0].message


def test_unknown_versions_are_not_compared() -> None:
    after = make_run(
        modules=[bump(SYSTEM_MODULES[0], None), SYSTEM_MODULES[1], *APP_MODULES]  # type: ignore[arg-type]
    )
    assert rules.module_version_changed(make_run(), after, CTX) == []


# --- EVENTLOG_NEW_ERRORS -----------------------------------------------------------------------


def test_eventlog_new_errors() -> None:
    findings = rules.eventlog_new_errors(make_run(), make_run(events=[make_event()]), CTX)
    assert ids(findings) == ["EVENTLOG_NEW_ERRORS"]
    assert findings[0].severity is Severity.HIGH
    assert "Contoso Service" in findings[0].message and "4242" in findings[0].message


def test_eventlog_ignores_events_seen_before_and_crash_events() -> None:
    known = make_event()
    crash = make_event(source="Application Error", event_id=1000)
    findings = rules.eventlog_new_errors(
        make_run(events=[known]), make_run(events=[known, crash]), CTX
    )
    assert findings == []


def test_eventlog_is_silent_without_event_data() -> None:
    assert (
        rules.eventlog_new_errors(make_run(no_events=True), make_run(events=[make_event()]), CTX)
        == []
    )


# --- ENV_CHANGED ----------------------------------------------------------------------------------


def test_environment_findings_cover_scalars_and_lists() -> None:
    before = make_environment()
    after = make_environment(ubr=4529, hotfixes=["KB5044284", "KB5050009"], display_version="24H2")
    findings = rules.environment_findings(before, after)
    assert {f.rule_id for f in findings} == {"ENV_CHANGED"}
    assert all(f.severity is Severity.INFO and f.app_id is None for f in findings)
    messages = [f.message for f in findings]
    assert "ubr 4351 -> 4529" in messages
    assert "hotfixes: added KB5050009; removed KB5043080" in messages
    assert len(findings) == 2


def test_identical_environments_have_no_findings() -> None:
    assert rules.environment_findings(make_environment(), make_environment()) == []


def test_list_delta() -> None:
    assert rules.list_delta(["a", "b"], ["b", "c"]) == (["c"], ["a"])
    assert rules.list_delta([], []) == ([], [])


# --- Juan's Phase 3 task (a) ------------------------------------------------------------------------
# Spec: window_title_changed(before, after, ctx) -> list[Finding]
#   * Compare before.launch.window_title with after.launch.window_title.
#   * Fire one INFO finding with rule id "WINDOW_TITLE_CHANGED" when both are
#     non-empty strings and differ. Put the old title in `before`, the new one
#     in `after`, and a message like 'window title "A" -> "B"'.
#   * Stay silent when either launch signal or either title is missing.
# Use the _finding helper like the other rules. Remove the skips when done.


@pytest.mark.skip(reason="TODO(juan): implement window_title_changed")
def test_window_title_changed_fires() -> None:
    after = make_run(launch=make_launch(window_title="Untitled - App (Compatibility Mode)"))
    findings = rules.window_title_changed(make_run(), after, CTX)
    assert ids(findings) == ["WINDOW_TITLE_CHANGED"]
    assert findings[0].severity is Severity.INFO
    assert findings[0].before == "Untitled - App"
    assert findings[0].after == "Untitled - App (Compatibility Mode)"


@pytest.mark.skip(reason="TODO(juan): implement window_title_changed")
def test_window_title_changed_is_silent_without_titles() -> None:
    untitled = make_run(launch=make_launch(window_title=None))
    assert rules.window_title_changed(make_run(), untitled, CTX) == []
    assert rules.window_title_changed(untitled, make_run(), CTX) == []
    assert rules.window_title_changed(make_run(), make_run(), CTX) == []


def test_exit_codes_show_hex_for_ntstatus_values() -> None:
    assert rules.format_exit_code(0) == "0"
    assert rules.format_exit_code(3) == "3"
    assert rules.format_exit_code(-1073741819) == "-1073741819 (0xC0000005)"
    assert rules.format_exit_code(3221225477) == "3221225477 (0xC0000005)"
