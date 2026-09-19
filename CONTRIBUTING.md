# Contributing to CompatSentinel

Thanks for looking at this. CompatSentinel is a small, focused tool and pull
requests are welcome, especially for new diff rules and collectors — see the
[good first issues](https://github.com/juandresrodca/CompatSentinel/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
for a place to start.

## Development setup

```bash
git clone https://github.com/juandresrodca/CompatSentinel
cd CompatSentinel
python -m venv .venv
.venv\Scripts\activate        # Windows; use `source .venv/bin/activate` elsewhere
python -m pip install -e ".[dev]"
pre-commit install
```

`compatsentinel doctor` should report your Python version and OS. Everything
except `capture` runs on Linux and macOS, so most contributions do not need a
Windows machine — the two recorded snapshots under `examples/snapshots` are
enough to develop and test `diff`, `report` and `mcp`.

## Before you open a pull request

```bash
ruff check .
ruff format --check .
mypy
pytest --cov
```

`pre-commit install` runs the first three automatically on commit. `mypy` is
strict across the whole package; a new module should stay that way rather
than opt out.

If you touch a collector or anything Windows-specific, also run:

```bash
pytest -m windows_only
```

on a real Windows machine, or let the `collector smoke (windows)` CI job do
it for you.

## What a good pull request looks like

- One logical change, with tests. A new diff rule needs a positive and a
  negative unit test in `tests/test_rules.py`, following the pattern of the
  existing rules in [`src/compatsentinel/diff/rules.py`](src/compatsentinel/diff/rules.py).
- [Conventional commits](https://www.conventionalcommits.org/) (`feat:`,
  `fix:`, `docs:`, `test:`, `chore:`, `ci:`), small and focused. Squash noisy
  work-in-progress commits before opening the PR.
- Update [`docs/DESIGN.md`](docs/DESIGN.md) when you make a decision future
  readers would need explained (a threshold, a data model choice, a Windows
  API quirk you had to work around).
- Update [`CHANGELOG.md`](CHANGELOG.md) under `## [Unreleased]`.

## Adding a diff rule

A rule is a pure function `(before: AppRun, after: AppRun, ctx: RuleContext)
-> list[Finding]` in `src/compatsentinel/diff/rules.py`, registered in the
`RULES` tuple. It must not touch the clock, the disk or the OS, and must stay
silent (return `[]`) when a signal it needs is `None` on either side — that
means the collector did not run, not that nothing changed. Look at
`module_missing` for the simplest example and `module_version_changed` for
one that reads `RuleContext`.

## Adding a collector

A collector is a class with `name`, `requires_elevation` and
`collect(ctx: RunContext)` in `src/compatsentinel/collectors/`, satisfying the
`Collector` protocol in `collectors/base.py` structurally — no base class to
inherit. Raise `CollectorSkipped` for "not applicable here"; anything else
you raise is caught by `run_collector` and recorded as an `error` result, so
a broken collector can never abort a capture. Verify the Windows API you plan
to use actually behaves the way you think before writing the collector —
see the "Phase 2" notes in `docs/DESIGN.md` for what that looked like here.

## Reporting a bug or requesting a feature

Use the issue templates; they ask for exactly what is needed to act on the
report (suite file, snapshot excerpt, OS build). For a security issue, see
[SECURITY.md](SECURITY.md) instead of opening a public issue.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
