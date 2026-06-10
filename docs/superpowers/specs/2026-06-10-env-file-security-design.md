# Environment Variable Env-File Security Design

## Goal

Prevent API keys and secrets from appearing in process listings when Docker
containers are launched. Currently `-e KEY=VALUE` arguments are embedded in the
`docker run` process argv, visible to any host user via `ps aux`,
`/proc/<pid>/cmdline`, and potentially Docker daemon audit logs. The fix
replaces inline `-e` flags with `--env-file` pointing to a temporary file that
is created with `0600` permissions and deleted immediately after the Docker
process exits.

## User-Facing Behavior

No change. Environment variable handling for `create`, `env set`, `run`,
`start`, `attach`, and `shell` works identically — values are still stored in
`environment.json` and passed to the container. The only difference is that
secrets no longer transit through the process command line.

## Architecture

Three changes, all in `src/aisbox/docker.py`:

### 1. New helper: `_env_file_for(env: dict[str, str]) -> ContextManager[str | None]`

A `@contextmanager` that writes the sorted env dict to a temp file (one
`KEY=VALUE` per line), creates it with `0600` permissions, yields the path, and
deletes the file on exit. Yields `None` when `env` is empty, avoiding
unnecessary temp file creation.

Usage:

```python
with _env_file_for(env.env) as env_file:
    # env_file is a path string or None
    ...
```

### 2. `container_command()` gains an optional `env_file: str | None = None` parameter

When `env_file` is provided and `env` is non-empty, the function appends
`["--env-file", env_file]` instead of the current `-e KEY=VALUE` loop. When
`env_file` is `None` and `env` is non-empty, it falls back to the old `-e`
behavior (preserving backward compatibility for tests or alternate callers
that don't use the env-file path).

### 3. `run_container()` wraps the runner call with the env-file context manager

```python
def run_container(env, agent, config_source, mode, ...):
    with _env_file_for(env.env) as env_file:
        runner(
            container_command(env, agent, config_source, mode, ..., env_file=env_file),
            check=True,
        )
```

The `with` block guarantees cleanup even if the Docker process fails or the
caller hits Ctrl-C.

### What doesn't change

`container_command()` still returns a plain `list[str]`. No return type change,
no API break for external callers. The new parameter has a default and is
backward compatible.

## Error Handling

- **Temp file creation failure** (disk full, permission denied on `/tmp`):
  raises `AisboxError` wrapping the original `OSError`, same pattern used
  throughout the codebase for managed state operations. The container is never
  launched.

- **Docker process failure** (non-zero exit): `subprocess.CalledProcessError` is
  raised as before — the `finally` block in the context manager still cleans up
  the temp file.

- **Keyboard interrupt / SIGTERM during run**: the context manager's `__exit__`
  runs during stack unwinding, so the temp file is removed.

- **Empty env dict**: `_env_file_for({})` is a no-op context manager — yields
  `None`, no temp file created, `container_command` receives `None` and produces
  neither `-e` nor `--env-file` arguments.

## Tests

### Unit tests (`tests/test_docker.py`)

- `_env_file_for` creates a temp file with correct `KEY=VALUE` content and
  `0600` permissions
- `_env_file_for` cleans up after the `with` block exits normally
- `_env_file_for` cleans up even when the `with` block raises
- `_env_file_for({})` is a no-op (no file created, yields `None`)
- `container_command(env_file=...)` produces `--env-file <path>` instead of
  `-e KEY=VALUE` entries
- `container_command(env_file=None)` still produces `-e KEY=VALUE` for backward
  compatibility

### Integration test

- `run_container` with env vars does not expose values in the command list
  passed to a mock runner (verify no `-e SECRET=` substring appears in the
  command)

## Scope

This design addresses only the process-listing leak via Docker `-e` flags. It
does not:

- Encrypt stored environment values in `environment.json`
- Integrate an external secret manager (Vault, etc.)
- Change how values are input or prompted in the CLI
- Modify Docker daemon logging behavior

The existing `0600` managed-state permissions and hidden prompting in
`cli.py:68` already address the other legs of the secret-handling story.
