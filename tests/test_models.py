"""Model contract tests: immutability, strictness and JSON round trips."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from compatsentinel.models import (
    SCHEMA_VERSION,
    LaunchOutcome,
    LaunchSignal,
    RunDefaults,
    Severity,
    Snapshot,
)
from tests.conftest import SnapshotFactory


def test_snapshot_round_trips_through_json(make_snapshot: SnapshotFactory) -> None:
    original = make_snapshot()
    restored = Snapshot.model_validate_json(original.model_dump_json())
    assert restored == original
    assert restored.schema_version == SCHEMA_VERSION


def test_enums_serialise_as_plain_strings(make_snapshot: SnapshotFactory) -> None:
    data = make_snapshot().model_dump(mode="json")
    assert data["apps"][0]["launch"]["outcome"] == "ok"
    assert Severity("critical") is Severity.CRITICAL


def test_models_are_frozen(make_snapshot: SnapshotFactory) -> None:
    snapshot = make_snapshot()
    with pytest.raises(ValidationError, match="frozen"):
        snapshot.label = "other"  # type: ignore[misc]


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        LaunchSignal(outcome=LaunchOutcome.OK, exit_cod=0)  # type: ignore[call-arg]


def test_run_defaults_reject_non_positive_values() -> None:
    with pytest.raises(ValidationError, match="timeout_seconds"):
        RunDefaults(timeout_seconds=0)


def test_snapshot_app_lookup(make_snapshot: SnapshotFactory) -> None:
    snapshot = make_snapshot()
    assert snapshot.app("notepad") is not None
    assert snapshot.app("missing") is None


def test_missing_signal_is_distinct_from_empty(make_snapshot: SnapshotFactory) -> None:
    run = make_snapshot().apps[0]
    assert run.events == []  # collector ran, found nothing
    assert run.modules is not None
    assert run.model_copy(update={"modules": None}).modules is None  # collector did not run
