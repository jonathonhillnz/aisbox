# Running Agents

`aisbox` offers three ways to run an agent: one-shot prompts, interactive
sessions, and a plain shell.

## Disposable containers

`aisbox run`, plain `aisbox start`, and `aisbox shell` use `docker run --rm`.
Docker removes the container when the command exits or the session ends. No
container filesystem state survives. For sessions you want to return to, see
[Retained Sessions](retained-sessions.md).

## One-shot: `aisbox run`

Pass a prompt and get a result. The container starts, the agent runs the
prompt, and the container is removed.

```bash
aisbox run -n <name> -- "your prompt here"
```

The `--` separates aisbox options from the prompt text. Everything after `--`
is joined into a single prompt string and passed to the agent.

Per-agent run modes:

| Agent | Command executed |
|-------|-----------------|
| `claude` | `claude -p <prompt>` |
| `codex` | `codex exec <prompt>` |
| `opencode` | `opencode run <prompt>` |

Temporary workspace and mount overrides are supported (see
[Workspaces & Persistence](workspaces.md)):

```bash
aisbox run -n <name> --workspace /path/to/temp -- "prompt"
aisbox run -n <name> --mount /path/to/dir alias -- "prompt"
```

## Interactive: `aisbox start`

Start an interactive agent session with a TTY:

```bash
aisbox start -n <name>
```

This attaches your terminal to the agent's interactive command (`claude`,
`codex`, or `opencode`). The container is disposable — it is removed when you
exit.

Use `--permission-policy default|auto|bypass` to choose the selected agent's
approval behavior for the interactive session:

```bash
aisbox start -n <name> --permission-policy auto
```

Temporary overrides are supported:

```bash
aisbox start -n <name> --workspace /path/to/temp
aisbox start -n <name> --mount /path/to/dir alias
```

To start a retained session you can detach from and reattach to, use
`--keep`. See [Retained Sessions](retained-sessions.md).

## Plain shell: `aisbox shell`

Open an interactive Bash shell inside the container without launching the
agent:

```bash
aisbox shell -n <name>
```

This gives you `/bin/bash` inside the container with the environment's
workspace, mounts, and environment variables available. The container is
disposable — it is removed when you exit.
