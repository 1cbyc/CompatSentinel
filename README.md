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

**Status:** early development. `capture`, `diff`, `report`, `mcp`, `doctor` and `validate` all exist today. Follow the
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

## Ask an AI assistant about your snapshots (MCP)

`compatsentinel mcp` runs a **read-only** [Model Context Protocol](https://modelcontextprotocol.io)
server over your stored snapshots. It exposes five tools:

| Tool | Purpose |
|---|---|
| `list_snapshots` | Labels of every stored snapshot |
| `get_environment(label)` | OS build, UBR, edition, hotfixes, runtimes |
| `get_app_run(label, app_id)` | Everything captured for one app in one snapshot |
| `diff(before, after, app_id?)` | Findings, score and verdict, same engine as the CLI |
| `explain_finding(rule_id)` | What a rule id means and its default severity |

and one resource, `snapshot://{label}`, for the raw snapshot JSON.

**Security model.** The server only reads exported snapshot files under the
directory you point it at. It never imports the code that launches or closes
applications, and a test (`test_server_never_imports_the_runner`) enforces
that in CI. No tool writes to disk, calls the network, or accepts a path
outside the configured store. This mirrors
[IntuneGraph](https://github.com/juandresrodca/IntuneGraph)'s posture: the
assistant reads exported data, nothing else.

### Claude Desktop configuration

Add this to `claude_desktop_config.json` (adjust the path to your snapshots):

```json
{
  "mcpServers": {
    "compatsentinel": {
      "command": "compatsentinel",
      "args": ["mcp", "--store", "C:/path/to/your/snapshots"]
    }
  }
}
```

Or, without a pipx install, point it at the repo's virtualenv Python and use
the bundled demo data:

```json
{
  "mcpServers": {
    "compatsentinel": {
      "command": "C:/path/to/CompatSentinel/.venv/Scripts/python.exe",
      "args": ["-m", "compatsentinel", "mcp", "--store", "C:/path/to/CompatSentinel/examples/snapshots"]
    }
  }
}
```

Test any MCP server, including this one, with the
[MCP Inspector](https://github.com/modelcontextprotocol/inspector) before
wiring it into an assistant:

```bash
npx @modelcontextprotocol/inspector compatsentinel mcp --store examples/snapshots
```

### Example conversation

Captured against the real server (`compatsentinel mcp --store examples/snapshots`)
through the MCP Inspector, using the demo snapshots from the 30-second try-it
section above.

> **You:** I have two CompatSentinel snapshots called "before" and "after".
> What changed for the app contoso-ledger?
>
> **Assistant:** *(calls `diff(before="before", after="after", app_id="contoso-ledger")`)*
>
> contoso-ledger went from **PASS** to **FAIL** (score 100/100), four findings:
>
> - **LAUNCH_FAILED** (critical) — it launched fine before; after, it exits
>   without showing its window.
> - **CRASH_NEW** (critical), twice — a WER report and an Application Error
>   event both point at `Contoso.Ledger.Native.dll`, exception `c0000005`
>   (access violation).
> - **EXIT_CODE_CHANGED** (high) — exit code `0` → `-1073741819` (`0xC0000005`,
>   the same access violation).
> - **EVENTLOG_NEW_ERRORS** (high) — a .NET Runtime 1026 event: an unhandled
>   `AccessViolationException` in `Contoso.Ledger.Native.Interop.OpenLedger`.
>
> This looks like a native interop crash triggered by the update, not a
> timing issue — the module list could not be compared because the app never
> stayed up long enough for the modules collector to run.
>
> **You:** What does CRASH_NEW mean exactly?
>
> **Assistant:** *(calls `explain_finding(rule_id="CRASH_NEW")`)*
>
> CRASH_NEW is a **critical** severity rule: it fires when a new Windows
> Error Reporting report or Application Error event is attributed to the app
> that was not present in the "before" snapshot.

## Design principles

- **Read-only and safe by design.** Never modifies system state beyond
  launching and closing the apps you list. No telemetry, no network calls.
- **Capture on Windows, analyse anywhere.** Diff, report and the MCP server
  run on Linux and macOS so contributors and CI do not need Windows.
- **Every finding explains itself.** Rule id, severity, before and after
  values, and a one-line explanation.



## License

[MIT](LICENSE)
