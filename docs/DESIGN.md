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
