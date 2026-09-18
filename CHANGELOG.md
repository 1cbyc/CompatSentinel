# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Data model (`models.py`): `Snapshot`, `Environment`, `AppRun`, collector signals, `Finding`, with a schema version.
- Suite loader with readable validation errors and `compatsentinel validate`.
- Versioned JSON snapshot store under `snapshots/<label>/snapshot.json` with atomic writes.
- `examples/apps.yaml`.
- Project scaffold: `pyproject.toml`, src layout, ruff, mypy, pytest, pre-commit.
- `compatsentinel doctor` reports Python, OS and whether pywin32 is available.
- CI on Ubuntu (lint, types, tests) and Windows (launch and close notepad).
