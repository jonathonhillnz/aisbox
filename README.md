# aisbox

`aisbox` runs Claude Code, Codex CLI, and OpenCode inside Docker containers.
Docker containers are disposable by default, with optional retained interactive
sessions. Workspaces and agent configuration persist through explicit mounts
and stored environment configuration.

> [!WARNING]
> **Public preview:** `aisbox` is intended for experimentation and feedback.
> Interfaces and workflows may change, and the project is not yet
> production-hardened.

## Safety Model

`aisbox` reduces accidental host exposure by creating isolated agent
environments, but Docker is not a complete security boundary. Review every
workspace and additional directory you mount.

- The configured state root (`<state-root>`) is `~/.aisbox` by default and is
  overridden by `AISBOX_HOME`.
- `aisbox` never automatically copies or mounts host credential state,
  including `~/.claude`, `~/.codex`, and `~/.ssh`. Explicit sensitive
  workspaces or mounts are writable and require confirmation or `--yes`.
- Docker runs as the current user. `aisbox` does not run Docker through `sudo`.
- Runtime containers are disposable by default. `start --keep` and `attach`
  explicitly retain one interactive container per environment until
  `aisbox kill`. A retained container's writable-layer state may contain
  sensitive data and is discarded when the container is removed. Durable
  persistence across container removal comes only from explicit bind mounts
  and stored environment configuration.
- `aisbox` creates managed state directories with mode `0700` and managed
  state files with mode `0600`, and tightens those permissions on subsequent
  writes.
- Containers use Docker's default outbound network access. Agents can send
  mounted or supplied data over the network, so mount only trusted, necessary
  data.
- Environment variable values are stored unencrypted in
  `<state-root>/<name>/environment.json`. The restrictive managed-state
  permissions reduce local exposure, but protect the state root as sensitive
  data.

## Requirements

- Supported hosts are POSIX systems (Linux and macOS). Native Windows hosts are
  not supported during the public preview.
- Python 3.11 or newer
- Docker access available to the current user without `sudo`
- `pipx` for the recommended CLI installation
- Network access for Docker image builds, which install Ubuntu packages and npm
  agent CLIs

Check Docker access with:

```bash
docker version
```

## Install From A Checkout

From an existing repository checkout:

```bash
pipx install .
```

## Quick Start

Create an environment with its own managed workspace:

```bash
aisbox create -n demo1 -a claude
```

Or use an existing source directory as the workspace:

```bash
aisbox create -n demo1 -a codex --workspace /path/to/source
```

Create an OpenCode environment:

```bash
aisbox create -n demo1 -a opencode --workspace /path/to/source
```

Set the environment as the default, run a prompt, and inspect the stored
configuration:

```bash
aisbox set default -n demo1
aisbox run -- "summarize this repository"
aisbox inspect
```

Pass `-n demo1` explicitly to override the default for commands that operate on
one environment.

## Supported Agents

| Agent | Create value | Run mode |
| --- | --- | --- |
| Claude Code | `claude` | `claude -p` |
| Codex CLI | `codex` | `codex exec` |
| OpenCode | `opencode` | `opencode run` |

Agent images are built locally during `aisbox create` and `aisbox rebuild`.
They include Git, OpenSSH client tools, GitHub CLI (`gh`), `nano`, and `vim`
alongside the selected agent CLI. GitHub and SSH authentication are configured
explicitly inside the environment shell, for example with `aisbox shell -n demo1`,
`ssh-keygen`, and `gh auth login`. Host credential directories are not copied or
mounted automatically.

## Permission Policies

`aisbox run` and `aisbox start` support
`--permission-policy default|auto|bypass` to choose how agent-level permissions
are configured for a runtime session.

`default` keeps the agent's default approval behavior. Use it when you want the
upstream agent CLI to decide whether to ask before writes, commands, or other
actions.

`auto` is recommended when the agent should edit files inside the selected
workspace without stopping for approval prompts, including CI-style
non-interactive runs:

```bash
aisbox run --permission-policy auto -- "update the tests"
aisbox start --permission-policy auto
```

`bypass` disables agent-level approval prompts and may also disable the
selected agent's own sandbox checks. Use it only inside trusted aisbox
containers with explicit workspace and mount choices:

```bash
aisbox run --permission-policy bypass -- "prototype the change"
aisbox start --permission-policy bypass
```

Policy mappings are agent-specific:

| Agent | `auto` mapping | `bypass` mapping |
| --- | --- | --- |
| Claude Code | `--permission-mode auto` | `--dangerously-skip-permissions` |
| Codex CLI | `--ask-for-approval never --sandbox workspace-write` | `--dangerously-bypass-approvals-and-sandbox` |
| OpenCode | maps to `--dangerously-skip-permissions` | maps to `--dangerously-skip-permissions` |

For `aisbox start --keep`, the permission policy is applied when the retained
container is created. Use `aisbox kill` before starting an existing retained
session with a different non-default policy.

## Authentication

Use `aisbox start -n demo1` to authenticate interactively inside a disposable
container. Alternatively, use an empty assignment to enter an API token at a
hidden prompt:

```bash
aisbox create -n demo1 -a claude -e ANTHROPIC_API_KEY=
aisbox env set -n demo1 -e OPENAI_API_KEY=
```

For OpenCode, start the TUI and run `/connect`:

```bash
aisbox start -n demo1
```

Use `/connect` to configure OpenCode Zen or another supported provider.
OpenCode also recognizes provider credentials supplied through the environment;
for example:

```bash
aisbox create -n demo1 -a opencode -e ANTHROPIC_API_KEY=
aisbox env set -n demo1 -e OPENAI_API_KEY=
```

OpenCode supports many providers. Its `opencode.json` configuration can
reference any environment variable supplied to the container using
`{env:NAME}`. Consult the OpenCode provider documentation for provider-specific
requirements.

An assignment ending in `=`, such as `OPENAI_API_KEY=`, opens one hidden prompt.
Press Enter at that prompt to store an empty value. Prompted values stay out of
shell history and normal command-line process inspection. Explicit non-empty
values remain supported and options can be repeated:

```bash
aisbox env set -n demo1 -e LOG_LEVEL=debug -e FEATURE_FLAG=enabled
aisbox env unset -n demo1 -e LOG_LEVEL -e FEATURE_FLAG
```

All values provided through `-e` or `aisbox env set` are stored unencrypted in
the environment's `environment.json`, and Docker receives them as environment
settings. Explicit non-empty command-line assignment values may remain in shell
history and, depending on the host, may be observable to local processes or
users. `aisbox` creates managed state directories with mode `0700` and managed
state files with mode `0600`, but credentials remain stored unencrypted.
Protect `AISBOX_HOME`, do not share tokens in logs or reports, and prefer
interactive authentication when suitable. `aisbox inspect` masks stored
values.

## Workspaces And Persistence

Without `--workspace`, the workspace is `<state-root>/<name>/files`. A supplied
workspace is mounted at `/workspace`.

Add and remove extra directory mounts by alias:

```bash
aisbox mount -n demo1 /path/to/dir dir
aisbox unmount -n demo1 dir
```

Use temporary workspace and mount overrides for a single runtime session:

```bash
aisbox run -n demo1 --workspace /path/to/temp/workspace "inspect this"
aisbox start -n demo1 --workspace /path/to/temp/workspace
aisbox start -n demo1 --mount /path/to/dir dir
aisbox attach -n demo1 --mount /path/to/dir dir
```

Temporary overrides are not saved to the environment. For disposable `run` and
plain `start`, they apply to one container only. For retained sessions, they
last until the retained container created with those overrides is killed or
replaced. When a retained session is already running, `attach` and
`start --keep` with overrides fail because running container mounts cannot be
changed.

The workspace and additional mounts are writable. Additional mounts appear at
`/workspace/<alias>` and expose the selected host directory to the agent. With
Docker's default outbound network access, agents can send mounted or supplied
data over the network; mount only trusted, necessary data.

When a newly supplied workspace or mount is a known credential directory,
inside one, or broad enough to contain one, `aisbox` displays the matching
paths and asks for confirmation. The default is No. Use `--yes` only when you
intend to give the agent read/write access to that sensitive host data.
Previously stored paths are not re-confirmed on every run.

Agent configuration persists under `<state-root>/<name>/config`. `aisbox run`,
plain `aisbox start`, and `aisbox shell` use `docker run --rm`; their containers
are removed after the container exits. Retained sessions are opt-in. Their
container filesystem can hold writable-layer state while the container exists,
but it is not durable persistence across container removal.

OpenCode may read project `CLAUDE.md` and `.claude/skills` files from the
mounted workspace through its upstream compatibility behavior. aisbox does not
automatically copy or mount host `~/.claude` state.

## Retained Sessions

Start a normal disposable interactive session with:

```bash
aisbox start -n demo1
```

Opt in to one retained container for the environment with:

```bash
aisbox start -n demo1 --keep
```

Detach without stopping the retained session by pressing `Ctrl-p Ctrl-q` in
sequence. `Ctrl-c` may stop the agent and retained session instead.

Reconnect, list running retained sessions, or stop and remove the retained
container:

```bash
aisbox attach -n demo1
aisbox sessions
aisbox kill -n demo1
```

`aisbox attach` uses one retained container per environment. It attaches to the
running container, creates it when it is missing, and replaces it when it is
stopped. The container captures the environment's mounts, environment
variables, and image when it is created. After configuration changes, run
`aisbox kill -n demo1` and recreate the retained session to apply them.

Retained container writable-layer filesystem changes survive detach and
reconnect until the retained container is killed or replaced. This state may
contain sensitive data and is discarded when the retained container is killed
or replaced. Durable persistence across container removal comes only from
explicit bind mounts and stored environment configuration; do not rely on the
retained container filesystem for durable persistence.

## Commands

```bash
aisbox create -n demo1 -a claude
aisbox list
aisbox inspect -n demo1
aisbox mount -n demo1 /path/to/dir dir
aisbox unmount -n demo1 dir
aisbox env set -n demo1 -e OPENAI_API_KEY=
aisbox env unset -n demo1 -e OPENAI_API_KEY
aisbox run -n demo1 -- "summarize this repository"
aisbox run -n demo1 --workspace /path/to/temp/workspace "prompt"
aisbox run -n demo1 --permission-policy auto -- "update the tests"
aisbox start -n demo1
aisbox start -n demo1 --permission-policy auto
aisbox start -n demo1 --mount /path/to/dir dir
aisbox start -n demo1 --keep
aisbox attach -n demo1
aisbox attach -n demo1 --mount /path/to/dir dir
aisbox sessions
aisbox kill -n demo1
aisbox shell -n demo1
aisbox rebuild -n demo1
aisbox set default -n demo1
aisbox doctor
aisbox delete -n demo1 --force
```

Run `aisbox --help` or `aisbox <command> --help` for current option details.

## Known Preview Limitations

- Only Claude Code, Codex CLI, and OpenCode are supported.
- Agent images are built locally and upstream CLI versions are not pinned.
- Mounts and stored environment variables are configured manually.
- Docker-backed integration tests are not part of the normal test suite.
- Compatibility and security response timelines are best-effort during the
  preview.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) before proposing a substantial change.
Report vulnerabilities according to [SECURITY.md](SECURITY.md), never through a
public issue.

Licensed under [Apache-2.0](LICENSE).
