"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    """A Click/Typer test runner that captures output without spawning a process."""
    return CliRunner()
