# Quick Start

This page gets you from zero to a running agent in a few commands.

## 1. Create an environment

Create an environment named `demo` with Claude Code and a managed workspace:

```bash
aisbox create -n demo -a claude
```

To use an existing source directory as the workspace instead, pass
`--workspace`:

```bash
aisbox create -n demo -a claude --workspace /path/to/source
```

The `--workspace` value must be an existing directory. Without `--workspace`,
aisbox creates a managed workspace at `<state-root>/demo/files`.

You can also create environments for `codex` or `opencode` by changing the
`-a` value.

## 2. Set a default environment

Set the environment as the default so you can omit `-n` on subsequent
commands:

```bash
aisbox set default -n demo
```

Commands that target a single environment will use the default when `-n` is
omitted. Pass `-n <name>` explicitly to operate on a different environment.

## 3. Run an agent

Pass a prompt directly:

```bash
aisbox run -- "summarize this repository"
```

The `--` separates aisbox options from the prompt text. The container is
disposable — Docker removes it after the command completes.

## 4. Inspect the environment

See the stored configuration:

```bash
aisbox inspect
```

`aisbox inspect` shows the environment name, agent, workspace path, image
tag, configured environment variable keys (values are masked), and mounts.

## Next steps

- [Environments](guide/environments.md) — the full environment lifecycle
- [Authentication](guide/authentication.md) — supply API keys and credentials
- [Running Agents](guide/running-agents.md) — interactive sessions, `shell`,
  and retained sessions
- [Workspaces & Persistence](guide/workspaces.md) — mounts and what persists
  across container runs
