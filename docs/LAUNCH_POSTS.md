# Launch posts (drafts)

Drafted for review before posting. None of these have been posted. Fill in
the demo GIF / screenshot link once `docs/demo.gif` exists, and swap the repo
URL if it changes. Each is written to lead with the problem, not the tool.

---

## r/sysadmin

**Title:** Built a free tool to check if Patch Tuesday broke your apps, before your users tell you

Every month it's the same routine: install updates on a test machine, poke
around a few apps by hand, hope you didn't miss anything, ship it to the
fleet. I got burned once by an update that silently dropped a DLL a
line-of-business app needed, and nobody noticed until three departments
called in the same afternoon.

So I built **CompatSentinel**: it launches a list of apps you define, records
what "normal" looks like (does it start, how fast, what DLLs it loads, does
it throw errors), then you install updates and run it again. It diffs the
two and tells you exactly what changed, with a risk score — crash = critical,
a DLL going missing = medium, a version bump on a system DLL after an OS
update = informational, that kind of thing.

- Read-only. It only launches and closes the apps you list, nothing else.
  No telemetry, no network calls, no admin rights needed for the default
  checks.
- Single-file HTML report you can attach to a change ticket.
- Free, MIT licensed: <https://github.com/juandresrodca/CompatSentinel>

You can try the diff and report against two example snapshots in the repo
without touching a Windows box at all, if you want to see what the output
looks like before running it for real.

Feedback and "you missed this obvious signal" comments very welcome — it's
early (v0.1.0) and I'd rather hear about gaps now.

---

## r/Intune

**Title:** Open source tool for validating app compatibility after Windows updates — thinking about an Intune-driven suite generator

Sharing something I built for the classic "did this month's update break
anything" problem: **CompatSentinel**. You give it a list of apps
(`apps.yaml`), it captures a behavioural fingerprint before and after an
update — launch success, startup time, loaded DLLs, event log errors, crash
reports — and diffs the two with a risk score per app.

It's read-only (launches and closes only what you list, nothing else, no
telemetry) and the diff/report/AI-assistant pieces run on any OS, so you can
review a capture taken on a device without needing Windows yourself.

I know a lot of you manage app inventories through Intune already, so
generating a suite file from an Intune app list (or winget) is on the
roadmap rather than built — if that's something you'd actually use, say so
in the issue, it'll move it up:
<https://github.com/juandresrodca/CompatSentinel/issues>.

Repo: <https://github.com/juandresrodca/CompatSentinel>

---

## r/PowerShell

**Title:** Wrote a Python CLI for app compatibility regression testing — curious how PS folks would want to drive it

I mostly live in PowerShell day to day, but built this one in Python because
it needed to run its diff and reporting on non-Windows CI. **CompatSentinel**
captures a behavioural fingerprint of a set of Windows apps (launch, startup
time, DLLs, event log errors, WER crash reports), then diffs two captures
and scores the regressions.

It's a standalone CLI (`pipx install`), not a module, but the suite file is
plain YAML and the snapshot output is plain JSON, so wrapping it from a
PowerShell script or scheduled task is straightforward — capture before
updates, capture after, diff, fail the pipeline on the exit code if you want.

Would genuinely like PowerShell-side feedback: is a `.psd1`-driven suite
format (instead of YAML) something people would actually reach for over
plain YAML? Opinions welcome on the issue tracker.

<https://github.com/juandresrodca/CompatSentinel>

---

## r/Python (Showcase)

**Title:** CompatSentinel — a Python CLI + MCP server that diffs "behavioural fingerprints" of Windows apps to catch update regressions

**What My Project Does**

CompatSentinel launches a list of Windows applications, records a
"behavioural fingerprint" (does it start, how fast, what DLLs it loads,
does it log errors or crash), and diffs two such captures — say, before and
after installing Windows updates — into a scored list of findings.

**Target Audience**

Sysadmins running monthly Windows update validation, and as a portfolio
piece it's also a fairly complete example of a typed, tested CLI: pydantic
v2 models everywhere data crosses a boundary, a plugin-style collector
protocol, a pure/deterministic diff engine (no I/O, no clock — that's most
of the test suite), a single-file offline HTML report built with Jinja2, and
a read-only MCP server on top of the same data so an AI assistant can answer
"what changed and why does it matter" questions.

**Comparison**

I haven't found another open source tool that does this specific
before/after behavioural diff for Windows app compatibility; closest
adjacent tools are Procmon (point-in-time trace, not a diff) and generic
UI test frameworks (which test *your* automation, not "did the update break
this app").

Repo, with a 30-second no-Windows-required demo:
<https://github.com/juandresrodca/CompatSentinel>

---

## r/mcp

**Title:** Read-only MCP server over Windows app compatibility diffs — ask an assistant "what broke after the update"

Built **CompatSentinel**, a tool that captures a behavioural fingerprint of
Windows apps and diffs two captures (e.g. before/after a Windows update)
into scored findings. On top of that it ships a small read-only MCP server:
`list_snapshots`, `get_environment`, `get_app_run`, `diff`, `explain_finding`,
plus a `snapshot://{label}` resource.

Security-wise the thing I care most about: the MCP server module does not
import the code that launches or closes processes at all, and there's a test
that fails CI if that ever changes — so it's read-only by construction, not
by convention. Tested against the real MCP Inspector CLI over stdio, and
there's a Claude Desktop config and a full example conversation in the
README.

Would love feedback from people who build MCP servers regularly — particularly
on tool granularity (five tools felt right for this domain, curious if
that's too many or too few) and on the resource-vs-tool split I made
(`snapshot://{label}` for the raw file, tools for everything derived).

<https://github.com/juandresrodca/CompatSentinel>

---

## LinkedIn

Shipped v0.1.0 of an open source side project: **CompatSentinel**, a CLI
that catches Windows application compatibility regressions before users hit
them.

The idea came from a familiar problem in enterprise Windows operations:
Patch Tuesday lands, you eyeball a handful of apps, and hope nothing subtle
broke. CompatSentinel automates that check — it captures a "behavioural
fingerprint" of a set of applications (does it launch, how fast, what DLLs
it loads, does it throw errors or crash), then diffs two captures with a
weighted risk score per app.

A few things I'm proud of on the engineering side:

- Read-only and safe by design — it only launches and closes the apps you
  list, no telemetry, no network calls, and the diff engine is pure and
  deterministic (no I/O, no clock), which is what let me get diff test
  coverage above 90%.
- Runs its capture on Windows 10/11, but diff, report and the MCP server run
  on any OS — CI validates both on GitHub Actions.
- A read-only Model Context Protocol server so an AI assistant can answer
  "what changed and why does it matter" over your captured data, without
  ever touching the machine.

It's MIT licensed and open for contributions:
https://github.com/juandresrodca/CompatSentinel

#Windows #DevOps #OpenSource #Python #MCP #SystemAdministration

---

## r/CharruaDevs (versión en español)

**Título:** CompatSentinel — herramienta open source para detectar regresiones de compatibilidad en apps de Windows tras una actualización

Comparto un proyecto personal: **CompatSentinel**, una CLI en Python que
captura una "huella de comportamiento" de un conjunto de aplicaciones de
Windows (si inicia, cuánto tarda, qué DLLs carga, si registra errores o
crashea) y compara dos capturas — por ejemplo, antes y después de instalar
actualizaciones de Windows — con un puntaje de riesgo por aplicación.

Es de solo lectura por diseño: únicamente abre y cierra las apps que le
indicás, sin telemetría ni llamadas de red. La captura corre en Windows
10/11, pero el diff, el reporte HTML y el servidor MCP (para conectarlo a un
asistente de IA) corren en cualquier sistema operativo, con CI verificando
ambos casos.

Está en v0.1.0, licencia MIT, y hay una demo de 30 segundos sin necesidad de
Windows en el propio repo:
<https://github.com/juandresrodca/CompatSentinel>

Cualquier feedback, bienvenido — especialmente si trabajás con
administración de sistemas Windows a diario y ves algo que le falte.
