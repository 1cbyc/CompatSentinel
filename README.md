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

**Status:** early development. `capture`, `diff`, `report`, `doctor` and `validate` exist today; `mcp` is next. Follow the
[changelog](CHANGELOG.md) and the roadmap in the issues.

## Try it in 30 seconds, no Windows required

The repository ships two recorded snapshots that tell a Patch Tuesday story:
a Windows 11 23H2 machine upgraded to 24H2. Notepad got slower, Calculator
lost a DLL, a line-of-business app started crashing, and WordPad is gone.

```bash
pipx install git+https://github.com/juandresrodca/CompatSentinel   # or the dev install below
compatsentinel diff examples/snapshots/before examples/snapshots/after
compatsentinel report examples/snapshots/before examples/snapshots/after --html report.html
```

The HTML report is a single offline file that follows your light or dark
theme. The demo data mixes real module lists from a Windows 11 capture with
fabricated apps and regressions; nothing in it identifies a real machine.

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



## License

[MIT](LICENSE)
