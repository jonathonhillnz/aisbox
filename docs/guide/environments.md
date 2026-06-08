# Environments

An environment is a named configuration that ties together an agent, a
workspace, additional mounts, and environment variables. Each environment is
stored under `<state-root>/<name>/`.

## Supported agents

| Agent | Alias | Run command | Interactive command |
|-------|-------|-------------|---------------------|
| Claude Code | `claude` | `claude -p` | `claude` |
| Codex CLI | `codex` | `codex exec` | `codex` |
| OpenCode | `opencode` | `opencode run` | `opencode` |

Agent images are built locally during `aisbox create` and `aisbox rebuild`.
The build starts from Ubuntu 24.04, installs the agent CLI globally via npm,
and runs as an unprivileged `aisbox` user.

## Creating an environment

```bash
aisbox create -n <name> -a <agent>
```

Required options:

| Option | Description |
|--------|-------------|
| `-n`, `--name` | Environment name. Must match `[a-zA-Z0-9_.-]+`. |
| `-a`, `--agent` | Agent alias: `claude`, `codex`, or `opencode`. |

Optional:

| Option | Description |
|--------|-------------|
| `--workspace` | Path to an existing directory to use as the workspace. |
| `-e`, `--env` | Set `KEY=VALUE` in the environment; an empty value prompts without echo. |

Without `--workspace`, aisbox creates a managed workspace at
`<state-root>/<name>/files`.

## Listing environments

```bash
aisbox list
```

Output shows each environment's name, agent, and workspace path. If no
environments exist, it prints `No environments found`.

## Inspecting an environment

```bash
aisbox inspect -n <name>
```

`aisbox inspect` shows the stored configuration: name, agent, workspace
path, image tag, environment variable keys (values are masked as `<set>`), and
mounts with their aliases and source paths.

## Setting a default environment

```bash
aisbox set default -n <name>
```

The default environment is used by commands that accept `-n` when the option
is omitted.

## Rebuilding an agent image

```bash
aisbox rebuild -n <name>
```

Rebuilds the Docker image for the environment's agent. Use this after
updating `aisbox` to pick up changes in the Dockerfile or agent CLI version.
Upstream CLI versions are not pinned — the latest available at build time is
installed.

## Deleting an environment

```bash
aisbox delete -n <name>
```

Prompts for confirmation. Use `--force` to skip the prompt:

```bash
aisbox delete -n <name> --force
```

Deletion removes the environment directory and all its contents, including the
managed workspace. If the environment is the current default, the default
setting is cleared. Kill any active retained session first with
`aisbox kill -n <name>`.
