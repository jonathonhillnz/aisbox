# Default Environment Design

## Goal

Allow users to set one default aisbox environment so environment-specific
commands can omit `-n/--name`. An explicit `-n/--name` always overrides the
saved default.

## User-Facing Behavior

Add a top-level `set` command group. The first supported setable is
`default`:

```bash
aisbox set default -n demo1
```

The command requires `-n/--name`, validates that the environment exists, saves
that name as the default, and prints:

```text
Default environment set to demo1
```

The following commands will accept optional `-n/--name`:

- `aisbox run`
- `aisbox attach`
- `aisbox shell`
- `aisbox inspect`
- `aisbox rebuild`
- `aisbox mount`
- `aisbox unmount`
- `aisbox env set`
- `aisbox env unset`
- `aisbox delete`

For these commands, aisbox resolves the effective environment name in this
order:

1. Use explicit `-n/--name` when provided.
2. Otherwise use the saved default environment.
3. Otherwise fail with a user-facing `AisboxError`:

```text
No environment specified and no default environment is set
```

`aisbox create`, `aisbox list`, `aisbox doctor`, and commands under
`aisbox set` do not use a default environment.

The `set` command group is the extension point for future user-configurable
aisbox settings. Future settings should be added as sibling subcommands, such
as `aisbox set <setting-name> ...`, without changing the existing
`aisbox set default` command shape.

## State Model

Store aisbox-level settings at the root of `EnvironmentStore.root`, next to
environment directories:

```text
<AISBOX_HOME>/settings.json
```

The file format is JSON:

```json
{
  "default_environment": "demo1"
}
```

This file is intentionally generic so future setables can be added as new keys
without creating a separate one-off metadata file per setting. `EnvironmentStore`
will expose methods to read and write settings, plus focused methods to set,
load, and clear the default environment name. Loading the default validates the
persisted name and verifies that the environment still exists. Setting the
default also verifies that the target environment exists.

If the current default environment is deleted, deletion clears the
`default_environment` key from `settings.json`. This prevents later commands
from following stale state while preserving unrelated future settings.

## Architecture

Keep default selection as store-level settings metadata, not as a field on each
environment record. The default is global aisbox state, and keeping it outside
`environment.json` avoids mutating environment records when users switch
defaults.

Keep command behavior functions mostly name-based. The CLI will resolve an
optional command-line name into a concrete environment name before calling
existing command-layer functions. A small helper in `cli.py` will centralize the
resolution so error handling and override behavior stay consistent.

CLI architecture will add:

- a top-level `set_app = typer.Typer(no_args_is_help=True)`
- `app.add_typer(set_app, name="set")`
- `@set_app.command("default")` for the default environment setting

This preserves `aisbox set <setting>` as the future expansion pattern.

Command-layer helpers will be added for default management:

- `set_default_environment(name, store=None) -> str`
- `resolve_environment_name(name, store=None) -> str`

The CLI `set default` command will call `set_default_environment`. Optional-name
commands will call the CLI resolution helper, which uses
`resolve_environment_name`.

## Error Handling

Expected failures continue to raise `AisboxError` and print without tracebacks:

- setting the default to a missing environment
- running an environment-specific command without `-n` and without a default
- loading corrupt settings JSON or an unsafe persisted default name

If `settings.json` contains an unsafe default environment name, aisbox fails
with the existing validation error path rather than using the value.

## Tests

Add store tests for:

- setting and loading the default environment
- rejecting a missing default target
- clearing the default when deleting the default environment
- rejecting unsafe persisted default names
- preserving unrelated settings keys when clearing the default

Add CLI tests for:

- `aisbox set default -n demo1`
- `aisbox run -- prompt` using the saved default
- explicit `-n` overriding the saved default
- missing default producing a clean error without a traceback
- `aisbox delete` clearing the saved default when deleting the default env

Update README command examples to document `aisbox set default -n demo1` and
using `aisbox run -- ...` without `-n`.

## Scope

This design does not add `aisbox get default`, `aisbox unset default`, default
markers in `aisbox list`, or automatic default selection during environment
creation. It also does not define any other setables yet. Those can be added as
future `aisbox set <setting-name>` subcommands and `settings.json` keys when
users need them.
