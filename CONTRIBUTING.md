# Contributing to aisbox

aisbox is in public preview. Bug reports, feature requests, documentation
improvements, and focused code contributions are welcome.

## Before Contributing

Search existing issues before opening a new issue or pull request. Never include
credentials, API tokens, private source code, or sensitive host paths in an
issue, discussion, test fixture, log, or pull request.

Discuss substantial behavior or design changes in an issue before starting
implementation. Typo fixes and small documentation corrections do not require
prior issue discussion.

Report security issues according to [SECURITY.md](SECURITY.md), not through
public issues, discussions, or other public channels.

## Development Setup

aisbox requires Python 3.11 or newer. Create a virtual environment and install
the editable development dependencies:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Run the full test suite:

```bash
pytest
```

Run a focused test while iterating:

```bash
pytest tests/test_cli_core.py
```

Run the CLI from the checkout:

```bash
python -m aisbox.cli --help
```

## Testing

- Use `tmp_path` and set `AISBOX_HOME` with `monkeypatch` for tests that mutate
  environment state.
- Mock Docker subprocess calls unless a test explicitly performs real Docker
  validation.
- Use Typer's `CliRunner` when testing command output, flags, or exit behavior.
- Preserve the rule that expected failures do not emit tracebacks.

## Pull Requests

Keep pull requests focused. Link the relevant issue for substantial changes and
include the exact test commands and results used as evidence.

Update `README.md` when changing user-facing commands, flags, installation
steps, behavior, or safety guarantees.

Preserve the safety contract:

- Do not copy or mount host `~/.claude`, `~/.codex`, or OpenCode user
  configuration and credential directories.
- Do not add unexpected or broader host mounts.
- Do not print, persist, or commit secrets.
- Do not add automatic `sudo` behavior for Docker.

Do not commit generated build output, local virtual environments, caches,
coverage output, Docker artifacts, or other machine-local files.

## License

By contributing, you agree that your contributions are licensed under the
Apache-2.0 license.
