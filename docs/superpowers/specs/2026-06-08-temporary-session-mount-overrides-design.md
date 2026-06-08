# Temporary Session Mount Overrides Design

## Summary

`aisbox` environments persist one workspace and zero or more named mounts.
Users sometimes need to run an agent against a different checkout or expose an
extra directory for one session without changing the saved environment.

This change adds temporary mount override flags to `run`, `start`, and
`attach`:

```text
aisbox run -n demo1 --workspace /path/to/temp/workspace "inspect this"
aisbox start -n demo1 --workspace /path/to/temp/workspace
aisbox start -n demo1 --mount /path/to/dir dir
aisbox attach -n demo1 --mount /path/to/dir dir
```

Overrides are applied only to the Docker container created by that command.
They are never written to the stored environment configuration.

## Command Behavior

`--workspace PATH` temporarily replaces the environment workspace bind mount.
The selected path is mounted at `/workspace` for the created container.

`--mount SOURCE ALIAS` temporarily adds an extra writable bind mount at
`/workspace/<ALIAS>`. The option can be repeated to add multiple temporary
mounts.

The flags are available on:

- `aisbox run`
- `aisbox start`
- `aisbox attach`

For disposable `run` and plain `start`, the overrides last only for the
single `docker run --rm` container.

For `start --keep`, overrides are captured by the retained container that is
created and last until that retained session is removed with `aisbox kill`.
The saved environment still remains unchanged.

For `attach`, overrides are accepted only when no retained session exists and
`attach` must create one. If a retained session already exists and any
override was supplied, aisbox fails with a clear error instead of silently
ignoring the flags.

## Validation

Temporary overrides use the same safety rules as persisted workspace and mount
configuration:

- `--workspace` must resolve to an existing directory.
- Each temporary mount source must resolve to an existing directory.
- Temporary mount aliases must be valid relative names under `/workspace`.
- A temporary mount alias must not duplicate a persisted mount alias.
- A temporary mount alias must not duplicate another temporary mount alias.

The command returns `AisboxError` for validation failures and does not emit a
traceback for expected user errors.

## Architecture

The command layer builds an in-memory runtime copy of the loaded
`Environment`. If `--workspace` is present, the copy has its `workspace`
replaced. If `--mount` is present, the copy has extra `Mount` entries appended
after the persisted mounts.

Docker command construction continues to receive an `Environment` object and
does not need to know whether mounts came from persisted configuration or a
temporary override. This keeps the persistence boundary in `commands.py` and
preserves the existing Docker command tests.

No temporary override data is saved to environment JSON, default environment
state, retained-session metadata, or any new sidecar file.

## Retained Session Semantics

A retained container captures its mounts when Docker creates it. aisbox cannot
change those mounts later with `docker attach`.

Therefore:

- `start --keep --workspace ...` or `start --keep --mount ...` applies the
  overrides when it creates a retained session.
- If `start --keep` or `attach` finds an existing retained session and no
  overrides were supplied, it attaches normally.
- If `start --keep` or `attach` finds an existing retained session and
  overrides were supplied, it fails and tells the user to run `aisbox kill`
  before starting a new session with different mounts.

Stopped retained containers are removed and replaced by the existing retained
session flow. Temporary overrides supplied to that replacement command apply
to the newly created retained container.

## Error Handling

Expected failures are reported as concise user-facing errors:

- missing or non-directory temporary workspace
- missing or non-directory temporary mount source
- invalid temporary mount alias
- duplicate temporary mount alias
- temporary mount alias colliding with persisted mount alias
- override flags supplied while attaching to an existing retained session
- Docker failures during container creation or attachment

The feature does not add automatic sudo behavior, host agent configuration
mounts, or implicit copying of credentials.

## Testing

Unit and CLI tests will cover:

- `run --workspace` passes a temporary workspace to Docker without saving it.
- `start --workspace` passes a temporary workspace to Docker without saving it.
- repeated `--mount SOURCE ALIAS` appends temporary mounts to Docker command
  construction without saving them.
- temporary mount aliases cannot duplicate persisted mount aliases.
- temporary mount aliases cannot duplicate each other.
- temporary workspace and mount sources must exist and be directories.
- `start --keep` uses overrides when creating or replacing a retained session.
- `attach` uses overrides when creating a missing retained session.
- `attach` and `start --keep` reject overrides when a retained session already
  exists.
- expected CLI validation failures return nonzero without a traceback.
- README command examples and safety text mention temporary lifetime and
  retained-session behavior.

## Documentation

`README.md` will document `--workspace` and repeatable `--mount SOURCE ALIAS`
on `run`, `start`, and `attach`. The docs will state that these flags are
temporary, do not update saved environment configuration, and for retained
sessions last only for the life of the retained container created by the
command.
