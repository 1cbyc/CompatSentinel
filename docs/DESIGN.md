# CompatSentinel design notes

Running record of the decisions behind the code and the trade-offs behind each
one. Written to be read before an interview, so every entry answers "why this,
and what did we give up".

## Phase 0: scaffold

### Package name

`compatsentinel` was free on PyPI and TestPyPI on 2026-09-18. The import name
and the distribution name are identical, which avoids the `pip install X` /
`import y` confusion that bites people with names like `pyyaml`/`yaml`.

### src layout

Code lives in `src/compatsentinel/`, not in a top-level `compatsentinel/`
folder. With the src layout the package is only importable once installed
(`pip install -e .`), so tests exercise the installed package and cannot pass
by accident because the working directory happens to be on `sys.path`.

### Build backend: hatchling

`pyproject.toml` is the single source of configuration (PEP 621). Hatchling is
small, standards based and reads the version from `__init__.py`, so there is
exactly one place to bump. Setuptools would also work; hatchling has fewer
legacy knobs to explain.

### Dependency policy

Runtime dependencies are added in the phase that first uses them. Phase 0
ships `typer`, `pydantic` and `rich` only. Windows-only packages (`pywin32`)
will use environment markers so `pip install compatsentinel` stays installable
on Linux and macOS, where diff, report and MCP must run.

### Type checking: mypy strict everywhere

The brief asked for strict mypy on the diff package. Starting strict for the
whole package is cheaper than tightening later: every module is small when it
is born. If a Windows collector has to call an untyped API, the relaxation is
done per module with a comment, never globally. The `pydantic.mypy` plugin
makes model constructors type checked (`init_typed`) and rejects unknown
fields (`init_forbid_extra`).

### Linting and formatting: ruff

One tool replaces flake8, isort, pyupgrade and black. `T20` bans stray
`print()` in library code so all user output goes through `rich`, which keeps
the CLI layer the only place that knows about terminals.

### Testing: pytest with strict markers

`--strict-markers` makes a typo in `@pytest.mark.windows_only` a hard error
instead of a silently unregistered marker. `xfail_strict = true` means a test
expected to fail that suddenly passes is a failure, which is how a planned
task announces it is done.

### CI: two jobs, two operating systems

- `ubuntu-latest`, Python 3.11 and 3.12: ruff, mypy, pytest with coverage,
  and a CLI sanity run. This is the job contributors care about.
- `windows-latest`: `doctor` plus a smoke test that launches and closes
  `notepad.exe`. It exists to prove that process control works on a hosted
  runner, which is where the Phase 2 collectors will be validated.

Only the `windows_only` marker selects the smoke test, so Linux CI never tries
to spawn a Windows binary.

### Finding: `notepad.exe` is a stub on Windows 11

Verified on a Windows 11 Home 26200 host on 2026-09-18: `subprocess.Popen(["notepad.exe"])`
returns a process that exits with code 0 within about a second, while a new
`Notepad.exe` (packaged app) appears under a different PID. On Windows Server,
which is what GitHub's `windows-latest` runs, notepad is the classic Win32 app
and the spawned PID stays alive.

Consequence for the launch collector: a fast exit with code 0 is **not** a
launch failure. The collector must snapshot process ids before launch, look for
new processes by image name after launch, and clean up only those. The Phase 0
smoke test already follows that pattern.

### `doctor` as a model, not a print

`doctor.collect()` returns a frozen pydantic `DoctorReport`; the CLI renders it
as a `rich` table. Separating data from presentation means the same report can
be emitted as JSON for bug reports and can be unit tested on any OS without
capturing stdout.

### Commit conventions

Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `ci:`),
one logical change per commit. Commits are authored by the project owner only.

## Phase 1: models, suite, store

### One strict base model

Every model inherits `StrictModel`, which sets `extra="forbid"` and
`frozen=True`. Forbidding extras turns a typo such as `windows_title_regex`
into an error that names the key, instead of a suite that silently never
matches a window. Freezing makes the diff engine safe: it receives snapshots
and cannot mutate them by accident, so two diffs of the same inputs always
agree.

Trade-off: strict models reject snapshots written by a *newer* tool that added
a field. That is intentional; the schema version check gives a clearer error
than a partially understood snapshot would.

### `None` versus empty list

`AppRun.modules`, `events` and `wer` are `list | None`. `None` means the
collector did not produce data (skipped, needs elevation, crashed). `[]` means
it ran and found nothing. Without that distinction, a collector failing on the
"after" side would look like every DLL vanished and every rule would fire.

### Schema version lives in the file, not the filename

`schema_version` is a plain integer field with a default. The store refuses
files newer than it understands and can add per-version migrations later.
Keeping it inside the JSON means a snapshot copied between machines or
attached to a ticket stays self describing.

### Suite validation errors are formatted, not re-raised

pydantic's `ValidationError` is precise but noisy. `format_validation_error`
flattens it to one line per problem in the form `apps.0.command: Field
required`, which is how a sysadmin counts entries in a YAML list. The
`SuiteError` message is the user interface; the original exception is chained
for debugging.

### Store layout and atomic writes

`snapshots/<label>/snapshot.json`. A directory per label leaves room for
sidecar files (HTML report, raw logs) without renaming anything. Writes go to
`snapshot.json.tmp` and are renamed into place, so a crash or Ctrl+C during
capture never leaves a truncated file that the diff would then misread.

`resolve()` accepts a label, a directory or a file so
`compatsentinel diff examples/snapshots/before examples/snapshots/after` works
from any working directory without a flag. Paths win over labels because a
path that exists is unambiguous; a label is a lookup.

### Labels are validated before touching disk

Labels become directory names. The pattern rejects path separators and
leading dots, so a label like `../etc` cannot escape the store root.

### Test fixtures use a factory, not JSON files, so far

`make_snapshot()` builds snapshots in code with overrides. Recorded JSON
fixtures arrive with the diff engine in Phase 3, once real captures exist to
record; until then a factory keeps tests short and typed.

## Phase 2: collectors and the environment fingerprint

### Verify first, then code

Every Windows API used here was exercised in a throwaway script on the
development machine before a line of collector code was written. That is how
the following facts were established, and each one changed the design:

- `notepad.exe` (System32) is a stub on Windows 11: exit code 0 within a
  second, real app under a new PID with no parent link.
- `EnumWindows` sees the packaged Notepad window about 480 ms after launch,
  and `GetWindowThreadProcessId` gives the real PID.
- `psutil.Process.memory_maps()` lists 115 DLLs for packaged Notepad without
  elevation.
- `GetFileVersionInfo` returns `FileVersionLS` as a *signed* 32-bit int;
  naive shifting prints negative build numbers.
- `EvtQuery` with an XPath filter works unelevated and returns events as XML.
- The registry says "Windows 10 Home" on Windows 11; only the build number
  tells them apart.
- Windows Error Reporting is **disabled** on the development machine
  (`Disabled = 1`), so no crash produces a `Report.wer` or an
  `Application Error` event there. That is why `doctor` now reports WER
  status and why the WER parser is verified against a fixture and the CI
  runner rather than locally.

### Process attribution instead of trusting the PID

An app run owns three sets of processes: the spawned tree, new processes with
the command's image name, and new processes that own a window matching
`window_title_regex`. "New" means not present in the PID snapshot taken just
before launch, which is what makes it safe to close them afterwards: a Notepad
the user already had open is never touched. The window regex is therefore not
only a readiness signal but the attribution mechanism for apps whose image
name differs from the command (`calc.exe` starts `CalculatorApp.exe`).

### Startup time is "time to first matching window"

Without a regex there is no startup timing, only an alive check. Alternatives
such as `WaitForInputIdle` were left out: they do not work across the stub
hand-off and would make the number mean different things for different apps.
One definition, documented, beats a clever fallback.

### Collectors are a Protocol, not a base class

`Collector` is a `typing.Protocol`: a class is a collector if it has `name`,
`requires_elevation` and `collect(ctx)`. There is nothing to inherit and no
registration step. `run_collector` is the only place that calls `collect`,
and it converts `CollectorSkipped` into `skipped` and any other exception
into `error`, so a collector cannot abort a capture.

The runner assigns each collector's result to a typed field of `AppRun`
explicitly rather than through a generic registry. Three collectors do not
justify indirection, and explicit assignment keeps mypy strict useful.

### Live versus post-run collectors

Modules must be read while the app is up, so the runner collects them on the
last launch before closing it. Event log and WER look at a time window, so
they run once after all launches. `RunContext` carries both the window and
the attributed PIDs and image names, which is all a collector may know.

### Event attribution is textual, on purpose

Application Error, .NET Runtime, SideBySide and WER events are logged by
*other* processes; the `Execution ProcessID` in the event is not the app's.
The app name appears in the event data instead, so events are matched by
image name in the raw data. Raw data is stored rather than the localized
message: it is language independent and does not require provider metadata.

### Platform guards as if/else

mypy runs with `platform = "win32"` on every OS so both CI jobs check the same
code paths, and `warn_unreachable` stays on. Code after an early
`if sys.platform != "win32": return` would be flagged unreachable, so platform
branches are always written as `if/else`. Windows-only imports (`win32gui`,
`winreg`) live inside those branches so every module imports on Linux.

### Environment sources

| Signal | Source | Needs elevation |
|---|---|---|
| build, UBR, DisplayVersion, EditionID | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion` | no |
| installed KBs | `Get-HotFix` (Win32_QuickFixEngineering) | no |
| .NET Framework | `NDP\v4\Full\Version` | no |
| .NET runtimes | `dotnet --list-runtimes` when on PATH | no |
| VC++ redistributables | Uninstall keys with "Visual C++" and "Redistributable" in the name | no |

`Get-HotFix` costs about three seconds, which is acceptable once per capture.
`wmic qfe` was rejected because WMIC is removed from recent Windows 11 builds.

### What the Windows CI job proves

`windows-latest` launches and closes notepad through `launch()`, then runs a
full `runner.capture` (two timed launches after a warmup) and asserts a
matching window, startup samples, System32 DLLs and a clean event log. A
final informational step crashes a throwaway interpreter to make the runner
write a real `Report.wer`, so the parser can be checked against genuine
output without enabling WER on a developer machine.

### Settle pause between launches

A first full run of the example suite reported notepad as `exited` although
every window was detected: on one of four back-to-back launches the packaged
Notepad process ended by itself within the alive check. Tracing five launches
with a half-second pause between close and relaunch showed no such exit. The
runner therefore waits `SETTLE_SECONDS` (1 s) between launches of the same
app. This is deliberately a constant, not a suite option: it is a tool
correctness margin, not a property of the app under test. If it turns out to
be app dependent it can move to `RunDefaults` later.

The exit code recorded for a stub-launched app is the stub's (0), not the real
process's. Reading the real exit code needs a handle opened before the process
ends; that is tracked as a follow-up issue rather than built now.

### Open verification item: crash reports on real crashes

On 2026-09-18 the `windows-latest` runner (WER enabled, `ForceQueue=1`,
`DontShowUI=1`) produced neither a `Report.wer` nor an `Application Error`
event within 30 s of a throwaway interpreter calling `os.abort()` and jumping
to a null function pointer. The parser therefore remains verified against the
documented format only. Until a genuine report is captured on a host where
WER is active, `CRASH_NEW` should be read as "best effort". This is tracked as
an issue for the launch milestone; the fastest route is a volunteer with WER
enabled running `compatsentinel capture` against an app known to crash.

## Phase 3: diff engine and scoring

### Rules are functions; the registry is a tuple

Each rule is `check(before: AppRun, after: AppRun, ctx) -> list[Finding]`, a
pure function with no I/O, clock or OS access. `RULES` is a tuple of `Rule`
records (id, default severity, one-line summary, function). Adding a rule is
one function plus one tuple entry, and the same table feeds documentation and
the MCP `explain_finding` tool, so the rule list can never drift from what
the engine actually runs.

Why not a class per rule? Eight rules of five to twenty lines each do not
need state or inheritance. A function is the smallest unit that can be unit
tested in isolation, which is where most of the tests live.

### Silence on missing data

A rule returns nothing when a signal is `None` on either side. A collector
that failed after the update must not look like every DLL vanished. The
engine lists such gaps in `AppDiff.unavailable_signals` so the report can say
"modules were not compared" instead of silently saying "no change".

### Scoring: each rule counts once per app

`score = min(100, Σ over rule ids of weight(worst severity for that rule))`
with weights critical 100, high 50, medium 20, info 0, and verdict thresholds
FAIL ≥ 50, WARN ≥ 20. Counting a rule once is the key decision: twenty
missing DLLs are one problem, and a Windows update that touches a hundred
system DLLs must not push every app to FAIL. The whole policy is three tables
in `scoring.py`.

### System DLL version changes and the environment

`MODULE_VERSION_CHANGED` is info by default and medium for a system DLL. But
after an OS update every system DLL changes version, and that is the
expected consequence of the update, not a signal. The rule therefore stays
info when the environment differs (`RuleContext.environment_changed`) and is
medium only when a system DLL changed *without* an OS change, which is the
genuinely suspicious case (a stray redistributable, a driver package, an
in-place file replacement).

### Crash evidence versus generic errors

`CRASH_NEW` counts WER reports and events from `Application Error` and
`Windows Error Reporting`. `EVENTLOG_NEW_ERRORS` excludes those providers so
one crash does not produce two findings. Evidence is compared as normalised
text against the before run, so a crash that already happened before the
update is not reported as new.

### `DiffResult` carries no timestamp

The engine must be deterministic: same inputs, same output. Adding "generated
at" would break equality between two runs and would leak the diffing host into
data meant to describe two other hosts. The CLI or report may add a timestamp
at render time.

### Demo snapshots are recorded plus fabricated, and the test says which

`examples/snapshots` tells one story, a 23H2 to 24H2 feature update: notepad
slower, calculator loses a DLL, a fictional LOB app crashes in its native
DLL, WordPad is gone because 24H2 removed it. The notepad and calculator
module lists come from a real capture, trimmed to fourteen system and
fourteen app modules each. `tests/test_engine.py` asserts the exact verdicts
and rule ids so the demo can never silently stop matching the README.

The recorded pair is the fixture for the diff tests as well. Keeping a second
copy under `tests/fixtures` would only create a drift risk.

### Exit codes for automation

`diff --fail-on {never,warn,fail}` maps the verdict to the exit status so a
Patch Tuesday pipeline can gate on it. The default fails only on FAIL because
WARN-level findings are expected after an OS update.
