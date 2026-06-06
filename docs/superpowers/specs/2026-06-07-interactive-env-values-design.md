# Interactive Environment Values Design

## Goal

Keep sensitive environment variable values out of shell history by prompting
for values when users supply an empty assignment. Align `aisbox env set` and
`aisbox env unset` with the repeatable `-e/--env` option used by
`aisbox create`.

## User-Facing Behavior

The `create` command continues to accept repeatable environment assignments:

```bash
aisbox create -n demo1 -a claude \
  -e ANTHROPIC_API_KEY= \
  -e SOME_SENSITIVE= \
  -e NOT_SENSITIVE=foo
```

Any assignment whose value is empty, such as `ANTHROPIC_API_KEY=`, triggers one
hidden prompt for that key. Explicit non-empty values are used without a
prompt. Assignments and prompts are processed in command-line order.

Pressing Enter at the hidden prompt is valid and stores an intentionally empty
value. The empty value in the command line is therefore always a prompt marker;
the prompt response determines the stored value, including an empty response.
Prompted values are not confirmed a second time.

The environment mutation commands replace their positional arguments with
required, repeatable `-e/--env` options:

```bash
aisbox env set -n demo1 \
  -e ANTHROPIC_API_KEY= \
  -e NOT_SENSITIVE=foo

aisbox env unset -n demo1 \
  -e ANTHROPIC_API_KEY \
  -e NOT_SENSITIVE
```

The old positional forms are not retained for compatibility. Each successful
mutation prints one redacted status line per supplied key:

```text
Set ANTHROPIC_API_KEY
Set NOT_SENSITIVE
```

and:

```text
Unset ANTHROPIC_API_KEY
Unset NOT_SENSITIVE
```

## Architecture

Terminal interaction remains in `src/aisbox/cli.py`. A shared CLI helper will
parse each `KEY=VALUE` assignment and call Typer's hidden-input prompt when the
parsed value is empty. The helper returns complete assignments to the command
layer, keeping prompting out of reusable behavior and storage code.

Parsing before prompting ensures an invalid key fails through the existing
`AisboxError` path without requesting a value. Prompting occurs before
environment creation or mutation begins.

The command layer will replace the single-item mutation functions with batch
operations:

- `set_env_vars(name, assignments, store=None) -> list[str]`
- `unset_env_vars(name, keys, store=None) -> list[str]`

Each operation loads and saves the environment once. It validates all supplied
items before mutating stored state, so a bad item cannot cause a partial
update.

For repeated set assignments, command-line order applies and the final value
for a duplicate key is stored. The returned key list preserves supplied order
so CLI output corresponds to the options the user entered.

For unset, every key must be a valid environment variable key and must exist in
the environment before any deletion occurs. Duplicate unset keys are invalid
because the same key cannot be removed twice; they fail with a clean
`AisboxError` and leave the environment unchanged.

## Secret Handling

Prompted input uses hidden terminal entry and is never printed in success or
error output. Existing `aisbox inspect` behavior continues to show keys while
masking values.

This change protects prompted values from shell history and normal command-line
process inspection. It does not change persistence: values remain stored
unencrypted in the environment's managed `environment.json`, protected by the
existing managed-state permissions.

Explicit non-empty assignments such as `-e TOKEN=value` remain supported, with
the existing warning that those values can remain in shell history or be
observable to local processes or users.

## Error Handling

Expected failures continue to use `AisboxError` and produce no traceback:

- malformed assignments that omit `=`
- invalid environment variable keys
- missing keys during `env unset`
- duplicate keys during `env unset`
- missing environment selection

Validation completes before mutation, and all prompts complete before invoking
the create or set command operation. A prompt abort, such as EOF or keyboard
interrupt, exits without creating or modifying an environment.

## Tests

CLI tests will cover:

- `create` prompting with hidden input for `KEY=`
- mixed prompted and explicit assignments
- storing an empty response from a hidden prompt
- multiple repeatable options for `env set`
- multiple repeatable options for `env unset`
- rejection of the removed positional forms
- prompted and explicit values remaining absent from command output
- clean failures without tracebacks

Command tests will cover:

- setting multiple variables with one load/save cycle
- final-value-wins behavior for duplicate set keys
- unsetting multiple existing variables
- atomic failure when any set assignment is invalid
- atomic failure when any unset key is invalid, missing, or duplicated

Repository documentation tests will assert that maintained examples use the
new option syntax and that the security guidance describes both the protection
and limitations of hidden prompting.

## Documentation

Update `README.md` wherever environment variables are configured:

- Authentication examples will demonstrate `KEY=` hidden prompting for
  sensitive values and retain an explicit non-empty example to show that both
  forms are supported.
- Security guidance will explain that hidden prompting keeps the entered value
  out of shell history and normal command-line process inspection, while the
  value remains stored unencrypted in managed state.
- The command reference will use repeatable `-e/--env` options for both
  `aisbox env set` and `aisbox env unset`.
- The text will state that pressing Enter at the hidden prompt stores an empty
  value.

Add concise Typer help text for `create`, `env set`, and `env unset` options so
`aisbox <command> --help` exposes the new syntax and prompt behavior without
requiring users to consult the README.

Update `tests/test_repository_docs.py` and any CLI help assertions needed to
prevent old positional examples or inaccurate secret-handling guidance from
returning.

`SECURITY.md` remains focused on private vulnerability reporting, and
`CONTRIBUTING.md` already requires README updates for user-facing command
changes, so neither file needs behavioral documentation changes. Existing
historical design and implementation artifacts under `docs/superpowers` remain
unchanged; this design and its implementation plan supersede their old command
examples.

## Scope

This design does not encrypt stored environment values, integrate an external
secret manager, read values automatically from the host environment, or add
confirmation prompts. It does not change Docker environment handling or
interactive agent authentication.
