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
