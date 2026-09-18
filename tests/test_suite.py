"""Suite loader tests. Each error case asserts the message names the culprit."""

from __future__ import annotations

from pathlib import Path

import pytest

from compatsentinel.models import RunDefaults
from compatsentinel.suite import AppSpec, SuiteError, load_suite

VALID = """
defaults:
  timeout_seconds: 20
apps:
  - id: notepad
    command: notepad.exe
    window_title_regex: "Notepad"
  - id: my-lob-app
    command: 'C:\\Program Files\\Contoso\\App.exe'
    args: ["--safe"]
    repeats: 5
    tags: [lob, dotnet]
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "apps.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_valid_suite_loads(tmp_path: Path) -> None:
    suite = load_suite(write(tmp_path, VALID))
    assert [app.id for app in suite.apps] == ["notepad", "my-lob-app"]
    assert suite.defaults.timeout_seconds == 20
    assert suite.defaults.repeats == 3  # untouched default
    assert suite.apps[1].args == ["--safe"]


def test_example_suite_is_valid() -> None:
    example = Path(__file__).parent.parent / "examples" / "apps.yaml"
    assert len(load_suite(example).apps) >= 2


def test_effective_settings_merge_overrides() -> None:
    app = AppSpec(id="x", command="x.exe", repeats=7)
    merged = app.effective(RunDefaults(timeout_seconds=10))
    assert merged == RunDefaults(timeout_seconds=10, repeats=7)


def test_missing_file_message(tmp_path: Path) -> None:
    with pytest.raises(SuiteError, match="not found"):
        load_suite(tmp_path / "nope.yaml")


def test_invalid_yaml_message(tmp_path: Path) -> None:
    with pytest.raises(SuiteError, match="invalid YAML"):
        load_suite(write(tmp_path, "apps: [\n  - id: notepad"))


def test_top_level_must_be_mapping(tmp_path: Path) -> None:
    with pytest.raises(SuiteError, match="top level must be a mapping"):
        load_suite(write(tmp_path, "- just\n- a list\n"))


def test_missing_command_points_at_the_app(tmp_path: Path) -> None:
    with pytest.raises(SuiteError, match=r"apps\.0\.command: Field required"):
        load_suite(write(tmp_path, "apps:\n  - id: notepad\n"))


def test_unknown_key_is_reported(tmp_path: Path) -> None:
    text = "apps:\n  - id: notepad\n    command: notepad.exe\n    windows_title_regex: x\n"
    with pytest.raises(SuiteError, match=r"apps\.0\.windows_title_regex: Extra inputs"):
        load_suite(write(tmp_path, text))


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    text = "apps:\n  - {id: a, command: a.exe}\n  - {id: a, command: b.exe}\n"
    with pytest.raises(SuiteError, match="duplicate app id"):
        load_suite(write(tmp_path, text))


def test_app_id_format(tmp_path: Path) -> None:
    with pytest.raises(SuiteError, match=r"apps\.0\.id: Value error, use lowercase"):
        load_suite(write(tmp_path, "apps:\n  - {id: 'Bad Id', command: a.exe}\n"))


def test_empty_apps_rejected(tmp_path: Path) -> None:
    with pytest.raises(SuiteError, match="apps: List should have at least 1 item"):
        load_suite(write(tmp_path, "apps: []\n"))


# --- Juan's Phase 1 task (a) ---------------------------------------------------
# Spec: window_title_regex must be a valid regular expression.
#   * Add a pydantic field validator on AppSpec.window_title_regex that calls
#     re.compile and, on re.error, raises ValueError with a message that starts
#     with "invalid regular expression:" and includes the original error text.
#   * None stays allowed.
#   * The error must surface through load_suite as a SuiteError pointing at
#     apps.N.window_title_regex, which pydantic does for you once the validator
#     raises ValueError.
# Remove the skip markers when done.


@pytest.mark.skip(reason="TODO(juan): validate window_title_regex compiles")
def test_invalid_regex_is_rejected(tmp_path: Path) -> None:
    text = "apps:\n  - id: a\n    command: a.exe\n    window_title_regex: '('\n"
    with pytest.raises(
        SuiteError, match=r"apps\.0\.window_title_regex.*invalid regular expression"
    ):
        load_suite(write(tmp_path, text))


@pytest.mark.skip(reason="TODO(juan): validate window_title_regex compiles")
def test_valid_regex_is_kept_verbatim() -> None:
    app = AppSpec(id="a", command="a.exe", window_title_regex=r"^Notepad(\s-\s.*)?$")
    assert app.window_title_regex == r"^Notepad(\s-\s.*)?$"
