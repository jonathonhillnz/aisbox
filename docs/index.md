# aisbox

`aisbox` runs Claude Code, Codex CLI, and OpenCode inside Docker containers.
Containers are disposable by default, with optional retained interactive
sessions. Workspaces and agent configuration persist through explicit mounts
and stored environment configuration.

!!! warning "Public preview"
    `aisbox` is intended for experimentation and feedback. Interfaces and
    workflows may change, and the project is not yet production-hardened.

## Disposable by default

Every `aisbox run`, plain `aisbox start`, and `aisbox shell` creates a
container with `docker run --rm`. When the command finishes or you exit the
interactive session, Docker removes the container. No container state survives
the exit.

For interactive work you want to return to, start a **retained session** with
`aisbox start --keep`. One retained container exists per environment until you
explicitly kill it. See [Retained Sessions](guide/retained-sessions.md) for
details.

## Supported agents

| Agent | Alias | Run mode |
|-------|-------|----------|
| Claude Code | `claude` | `claude -p` |
| Codex CLI | `codex` | `codex exec` |
| OpenCode | `opencode` | `opencode run` |

Agent images are built locally during `aisbox create` and `aisbox rebuild`.
Each image starts from Ubuntu 24.04, installs the agent CLI via npm, and runs
as an unprivileged `aisbox` user inside the container.

## Where to go next

- [Installation](installation.md) — requirements and setup
- [Quick Start](quickstart.md) — first run in a few commands
- [Environments](guide/environments.md) — creating and managing environments
- [Running Agents](guide/running-agents.md) — `run`, `start`, and `shell`
- [Authentication](guide/authentication.md) — providing credentials to agents
- [Workspaces & Persistence](guide/workspaces.md) — mounts and what persists
- [Retained Sessions](guide/retained-sessions.md) — interactive sessions you
  can detach from and reattach to
- [Command Reference](reference/commands.md) — every command and its options
- [Safety Model](safety.md) — isolation boundaries and what to watch for
- [Preview Limitations](limitations.md) — known gaps during the public preview
