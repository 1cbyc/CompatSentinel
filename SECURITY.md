# Security Policy

## Design intent

CompatSentinel is **read-only and safe by design**:

- `capture` never modifies system state beyond launching and closing the
  exact apps listed in your suite file. It makes no registry, filesystem, or
  service changes.
- Capture works without administrator rights where possible. Any signal that
  needs elevation is optional and clearly labelled as `skipped` rather than
  silently failing or prompting for elevation.
- No telemetry and no network calls, anywhere in the tool. `diff`, `report`
  and `mcp` operate entirely on local snapshot files.
- The MCP server (`compatsentinel mcp`) is read-only: it exposes stored
  snapshot data to an AI assistant and cannot launch, close, or otherwise
  touch a process. This is enforced by a test that fails CI if the server
  module ever imports the runner or a collector.

If you believe any of the above is violated by the actual behaviour of the
code, that is a security bug — please report it privately (see below), not
as a public issue.

## Supported versions

CompatSentinel is pre-1.0. Security fixes land on `main` and are released as
a new version; only the latest published release is supported.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for a security report.

Use GitHub's private vulnerability reporting for this repository:
[Report a vulnerability](https://github.com/juandresrodca/CompatSentinel/security/advisories/new).
If that is not available to you, email the maintainer listed on the
[GitHub profile](https://github.com/juandresrodca) with a subject line
starting `SECURITY:`.

Please include:

- What you found and why it matters (e.g. a way for `capture` to modify
  something outside the launched app, or for `mcp` to touch the system).
- Steps to reproduce, including your suite file if relevant.
- The `compatsentinel doctor` output and your OS version.

You should get an initial response within 5 business days. Please give a
reasonable amount of time to fix an issue before any public disclosure.

## Scope

In scope: the `compatsentinel` CLI and MCP server as published on PyPI and in
this repository. Third-party applications you choose to point CompatSentinel
at are out of scope.
