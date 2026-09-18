# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `compatsentinel diff`: pure, deterministic comparison of two snapshots with eight rules (LAUNCH_FAILED, CRASH_NEW, EXIT_CODE_CHANGED, STARTUP_REGRESSION, MODULE_MISSING, MODULE_VERSION_CHANGED, EVENTLOG_NEW_ERRORS, ENV_CHANGED), a per-app risk score and PASS/WARN/FAIL verdicts, `--json` export and `--fail-on` exit codes.
- Demo snapshots under `examples/snapshots` (23H2 to 24H2 upgrade story) that run on any OS.
- `compatsentinel capture`: launches each app in the suite with process attribution, window detection and startup timing, then records loaded modules, Application log errors and WER reports.
- Environment fingerprint: build, UBR, display version, edition, hotfixes, .NET and VC++ runtimes.
- `doctor` reports whether Windows Error Reporting is enabled.
- Data model (`models.py`): `Snapshot`, `Environment`, `AppRun`, collector signals, `Finding`, with a schema version.
- Suite loader with readable validation errors and `compatsentinel validate`.
- Versioned JSON snapshot store under `snapshots/<label>/snapshot.json` with atomic writes.
- `examples/apps.yaml`.
- Project scaffold: `pyproject.toml`, src layout, ruff, mypy, pytest, pre-commit.
- `compatsentinel doctor` reports Python, OS and whether pywin32 is available.
- CI on Ubuntu (lint, types, tests) and Windows (launch and close notepad).
