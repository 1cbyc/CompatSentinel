"""Load and validate the suite file (``apps.yaml``).

The suite is the only input a user writes by hand, so validation errors must
point at the exact key and say what is wrong in plain words.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import Field, PositiveInt, ValidationError, field_validator, model_validator

from compatsentinel.models import RunDefaults, StrictModel

APP_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class SuiteError(Exception):
    """Raised for any problem with the suite file. The message is user facing."""


class AppSpec(StrictModel):
    """One application to exercise."""

    id: str
    command: str = Field(min_length=1)
    args: list[str] = Field(default_factory=list)
    window_title_regex: str | None = None
    tags: list[str] = Field(default_factory=list)
    # Optional per-app overrides of RunDefaults.
    timeout_seconds: PositiveInt | None = None
    alive_check_seconds: PositiveInt | None = None
    repeats: PositiveInt | None = None
    warmup_runs: int | None = Field(default=None, ge=0)

    @field_validator("id")
    @classmethod
    def _id_is_safe(cls, value: str) -> str:
        # Ids end up in file names and CLI arguments, so keep them boring.
        if not APP_ID_PATTERN.match(value):
            raise ValueError(
                "use lowercase letters, digits, '.', '_' or '-' (max 64 chars), e.g. 'my-lob-app'"
            )
        return value

    def effective(self, defaults: RunDefaults) -> RunDefaults:
        """Merge the suite defaults with this app's overrides."""
        overrides = {
            name: value
            for name in RunDefaults.model_fields
            if (value := getattr(self, name)) is not None
        }
        return defaults.model_copy(update=overrides)


class Suite(StrictModel):
    defaults: RunDefaults = RunDefaults()
    apps: list[AppSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _ids_are_unique(self) -> Suite:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for app in self.apps:
            (duplicates if app.id in seen else seen).add(app.id)
        if duplicates:
            raise ValueError(f"duplicate app id(s): {', '.join(sorted(duplicates))}")
        return self


def load_suite(path: Path) -> Suite:
    """Read ``path`` and return a validated :class:`Suite`.

    Raises :class:`SuiteError` with a readable message for a missing file,
    malformed YAML or a schema violation.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SuiteError(f"suite file not found: {path}") from None
    except OSError as exc:
        raise SuiteError(f"cannot read suite file {path}: {exc}") from exc

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SuiteError(f"{path}: invalid YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise SuiteError(f"{path}: top level must be a mapping with an 'apps' list")

    try:
        return Suite.model_validate(data)
    except ValidationError as exc:
        raise SuiteError(format_validation_error(path, exc)) from exc


def format_validation_error(path: Path, error: ValidationError) -> str:
    """Turn pydantic's error list into one line per problem, prefixed by the key path.

    List indexes are ints in ``loc``; ``apps.0.command`` reads well enough and
    matches how people count entries in the file.
    """
    lines = [f"{path}: {error.error_count()} problem(s) in suite file"]
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"]) or "<root>"
        lines.append(f"  - {location}: {item['msg']}")
    return "\n".join(lines)
