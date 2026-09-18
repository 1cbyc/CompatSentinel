# CompatSentinel

> Catch Windows app compatibility regressions before your users do.

CompatSentinel captures the **behavioural fingerprint** of a set of Windows
applications (launch success, startup time, loaded DLLs, event log errors,
crash reports) and diffs two captures to flag regressions with a risk score.
Run it before and after Patch Tuesday, across two OS builds, or between two
machine configurations.

```text
compatsentinel capture --suite apps.yaml --label before
# install updates, reboot, or move to another build
compatsentinel capture --suite apps.yaml --label after
compatsentinel diff before after --html report.html
compatsentinel mcp            # expose snapshots to an AI assistant, read-only
```

**Status:** early development. `doctor` and `validate` exist today. Follow the
[changelog](CHANGELOG.md) and the roadmap in the issues.

## Install (development)

```bash
git clone https://github.com/juandresrodca/CompatSentinel
cd CompatSentinel
python -m venv .venv && .venv\Scripts\activate   # or: source .venv/bin/activate
python -m pip install -e ".[dev]"
pre-commit install
compatsentinel doctor
```

## Design principles

- **Read-only and safe by design.** Never modifies system state beyond
  launching and closing the apps you list. No telemetry, no network calls.
- **Capture on Windows, analyse anywhere.** Diff, report and the MCP server
  run on Linux and macOS so contributors and CI do not need Windows.
- **Every finding explains itself.** Rule id, severity, before and after
  values, and a one-line explanation.

See [docs/DESIGN.md](docs/DESIGN.md) for the key decisions and trade-offs.

## License

[MIT](LICENSE)
