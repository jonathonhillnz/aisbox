# Command Reference

This page documents every `aisbox` command with its options. Run
`aisbox --help` or `aisbox <command> --help` for current details.

## Conventions

- `<name>` — an environment name matching `[a-zA-Z0-9_.-]+`.
- `<agent>` — one of `claude`, `codex`, or `opencode`.
- `-n` is required unless a default environment has been set with
  `aisbox set default`.

## `aisbox create`

Create a new environment.

```bash
aisbox create -n <name> -a <agent> [--workspace <path>] [-e KEY=VALUE ...] [--yes]
```

| Option | Required | Description |
|--------|----------|-------------|
| `-n`, `--name` | Yes | Environment name. |
| `-a`, `--agent` | Yes | Agent alias. |
| `--workspace` | No | Path to an existing directory to use as workspace. |
| `-e`, `--env` | No | Set `KEY=VALUE`; an empty value prompts without echo. Repeatable. |
| `--yes` | No | Acknowledge sensitive workspace or mount paths. |

Example:

```bash
aisbox create -n demo -a claude
aisbox create -n demo -a codex --workspace /home/user/project
aisbox create -n demo -a opencode -e OPENAI_API_KEY=
```

## `aisbox list`

List all environments.

```bash
aisbox list
```

Prints `No environments found` if none exist.

## `aisbox inspect`

Show the configuration of an environment. Values are masked.

```bash
aisbox inspect [-n <name>]
```

## `aisbox mount`

Add a persistent directory mount to an environment.

```bash
aisbox mount [-n <name>] <source> <alias> [--yes]
```

| Argument | Description |
|----------|-------------|
| `source` | Path to an existing host directory. |
| `alias` | Mount name; appears at `/workspace/<alias>`. |

| Option | Description |
|--------|-------------|
| `--yes` | Acknowledge sensitive workspace or mount paths. |

Example:

```bash
aisbox mount -n demo /home/user/data data
```

## `aisbox unmount`

Remove a persistent mount by alias.

```bash
aisbox unmount [-n <name>] <alias>
```

Example:

```bash
aisbox unmount -n demo data
```

## `aisbox env set`

Set environment variables in the environment configuration.

```bash
aisbox env set -e KEY=VALUE ... [-n <name>]
```

| Option | Required | Description |
|--------|----------|-------------|
| `-e`, `--env` | Yes | `KEY=VALUE`; an empty value prompts without echo. Repeatable. |
| `-n`, `--name` | No | Environment name. |

Example:

```bash
aisbox env set -n demo -e OPENAI_API_KEY=
aisbox env set -n demo -e LOG_LEVEL=debug -e FEATURE_FLAG=enabled
```

## `aisbox env unset`

Remove environment variables from the environment configuration.

```bash
aisbox env unset -e KEY ... [-n <name>]
```

| Option | Required | Description |
|--------|----------|-------------|
| `-e`, `--env` | Yes | Environment variable key to remove. Repeatable. |
| `-n`, `--name` | No | Environment name. |

Example:

```bash
aisbox env unset -n demo -e LOG_LEVEL -e FEATURE_FLAG
```

## `aisbox run`

Run a one-shot prompt in a disposable container.

```bash
aisbox run [-n <name>] [--workspace <path>] [--permission-policy <policy>] [--mount <source> <alias> ...] [--yes] -- <prompt>
```

| Option | Description |
|--------|-------------|
| `-n`, `--name` | Environment name. |
| `--workspace` | Temporary workspace override for this run. |
| `--permission-policy` | Agent permission policy: `default`, `auto`, or `bypass`. |
| `--mount` | Temporary mount override (`SOURCE ALIAS`). Repeatable. |
| `--yes` | Acknowledge sensitive workspace or mount paths. |

Everything after `--` is joined into the prompt string. The container is
removed on exit.

Example:

```bash
aisbox run -n demo -- "explain this codebase"
aisbox run -n demo --workspace /tmp/other -- "check for issues"
aisbox run -n demo --mount /host/data data -- "analyze the data"
aisbox run -n demo --permission-policy auto -- "update the tests"
```

## `aisbox start`

Start an interactive agent session.

```bash
aisbox start [-n <name>] [--keep] [--workspace <path>] [--permission-policy <policy>] [--mount <source> <alias> ...] [--yes]
```

| Option | Description |
|--------|-------------|
| `-n`, `--name` | Environment name. |
| `--keep` | Retain the container for later attachment. |
| `--workspace` | Temporary workspace override. |
| `--permission-policy` | Agent permission policy: `default`, `auto`, or `bypass`. |
| `--mount` | Temporary mount override (`SOURCE ALIAS`). Repeatable. |
| `--yes` | Acknowledge sensitive workspace or mount paths. |

Without `--keep`, the container is disposable (`--rm`). With `--keep`, the
container is retained for later `attach`. For an existing running retained
session, use `aisbox kill` before starting with a different non-default
permission policy.

Example:

```bash
aisbox start -n demo
aisbox start -n demo --permission-policy auto
aisbox start -n demo --keep
aisbox start -n demo --workspace /tmp/other
```

## `aisbox attach`

Attach to a retained session, creating one if needed.

```bash
aisbox attach [-n <name>] [--workspace <path>] [--mount <source> <alias> ...] [--yes]
```

| Option | Description |
|--------|-------------|
| `-n`, `--name` | Environment name. |
| `--workspace` | Temporary workspace override. |
| `--mount` | Temporary mount override (`SOURCE ALIAS`). Repeatable. |
| `--yes` | Acknowledge sensitive workspace or mount paths. |

Fails with overrides if a retained session is already running.

Example:

```bash
aisbox attach -n demo
aisbox attach -n demo --mount /host/data data
```

## `aisbox sessions`

List running retained sessions.

```bash
aisbox sessions
```

Prints `No retained sessions found` if none exist.

## `aisbox kill`

Stop and remove a retained session.

```bash
aisbox kill [-n <name>]
```

Example:

```bash
aisbox kill -n demo
```

## `aisbox shell`

Open an interactive Bash shell inside the container.

```bash
aisbox shell [-n <name>]
```

The container is disposable — removed on exit.

## `aisbox rebuild`

Rebuild the Docker image for the environment's agent. Use this after updating
aisbox to pick up image changes such as added command-line tools.

```bash
aisbox rebuild [-n <name>]
```

## `aisbox set default`

Set the default environment.

```bash
aisbox set default -n <name>
```

## `aisbox doctor`

Run a health check on the aisbox installation.

```bash
aisbox doctor
```

Checks Docker availability, reports whether Docker is rootless, checks
state-directory writability, and lists the supported agents. Exits with a
non-zero status if a required check fails. Rootful Docker is reported as a
warning because rootless Docker is recommended on Linux.

## `aisbox delete`

Delete an environment and all its state.

```bash
aisbox delete [-n <name>] [--force]
```

| Option | Description |
|--------|-------------|
| `-n`, `--name` | Environment name. |
| `--force` | Skip confirmation prompt. |

Fails if the environment has an active retained session. Removes the
environment directory, managed workspace, and configuration. If the
environment is the current default, the default is cleared.

## Global options

| Option | Description |
|--------|-------------|
| `--version` | Show version and exit. |
| `--help` | Show help for `aisbox` or a subcommand. |
