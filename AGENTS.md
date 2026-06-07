# AGENTS.md

Guidance for agents working in this repository.

## Project Overview

`aisbox` is a Python CLI for running AI coding agents inside isolated Docker
environments. The package is implemented under `src/aisbox` and tested with
pytest under `tests`.

Core safety contract:

- Environment state is stored under `~/.aisbox/<name>` by default, or
  `AISBOX_HOME` when set.
- Host `~/.claude` and `~/.codex` directories must not be copied or mounted.
- Docker is invoked as the current user. Do not add automatic `sudo` behavior.
- Runtime containers are disposable by default. Retained sessions are explicit
  and removed with `aisbox kill`. Durable persistence after container removal
  comes from explicit bind mounts and stored environment config.

## Repository Layout

- `src/aisbox/`: source package
- `tests/`: pytest suite
- `README.md`: user-facing installation and command reference
- `pyproject.toml`: package metadata, dependencies, pytest configuration
- `docs/superpowers/`: planning/design artifacts
- `build/`: generated output if present; do not edit by hand

## Development Commands

Set up a local environment:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Run tests:

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

## Coding Conventions

- Target Python 3.11 or newer.
- Keep source imports rooted in the `src` package layout.
- Prefer small functions with explicit error paths using `AisboxError` for
  user-facing failures.
- Keep CLI presentation in `src/aisbox/cli.py`; keep behavior and state
  mutation in command/store/docker modules.
- Do not print secrets. Existing inspect output shows env keys but masks values.
- Use standard-library path handling (`pathlib.Path`) for filesystem work.
- Keep comments sparse and only where they clarify non-obvious behavior.

## Testing Guidance

- Add or update tests for behavior changes.
- Use `tmp_path` and `monkeypatch.setenv("AISBOX_HOME", ...)` for stateful tests.
- Mock Docker subprocess calls unless the task explicitly asks for real Docker
  validation.
- Test CLI behavior through Typer's `CliRunner` when changing command output,
  flags, or exit behavior.
- Preserve tests that check errors do not emit tracebacks for expected failures.

## Documentation Expectations

- Update `README.md` when adding, removing, or changing user-facing commands,
  flags, install steps, or safety guarantees.
- Keep command examples accurate and runnable from a normal shell.
- If design or planning docs conflict with implemented behavior, either update
  the user-facing docs or call out the mismatch in the final response.

## Git And Generated Files

- Do not revert unrelated user changes.
- Do not edit generated `build/` files by hand.
- Avoid committing local virtualenvs, caches, coverage output, or Docker build
  artifacts.
