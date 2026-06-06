# aisbox

`aisbox` runs Claude Code and Codex CLI inside disposable Docker containers,
with explicit persistence for workspaces and agent configuration.

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
- Host `~/.claude` and `~/.codex` directories are not copied or mounted.
- Docker runs as the current user. `aisbox` does not run Docker through `sudo`.
- Runtime containers are disposable. Persistence comes from explicit bind
  mounts and stored environment configuration.
- Containers use Docker's default outbound network access. Agents can send
  mounted or supplied data over the network, so mount only trusted, necessary
  data.
- Environment variable values are stored unencrypted in
  `<state-root>/<name>/environment.json`. Protect the state root and its
  permissions as sensitive data.

## Requirements

- Python 3.11 or newer
- Docker Engine available to the current user without `sudo`
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

Agent images are built locally during `aisbox create` and `aisbox rebuild`.

## Authentication

Use `aisbox attach -n demo1` to authenticate interactively inside the
environment, or provide API tokens explicitly:

```bash
aisbox create -n demo1 -a claude -e ANTHROPIC_API_KEY=value
aisbox env set -n demo1 OPENAI_API_KEY=value
```

Values provided through `-e` or `aisbox env set` are stored unencrypted in the
environment's `environment.json`, and Docker receives them as environment
settings. Command-line assignment values may remain in shell history and,
depending on the host, may be observable to local processes or users. Protect
`AISBOX_HOME` and state permissions, do not share tokens in logs or reports,
and prefer interactive authentication when suitable. `aisbox inspect` masks
stored values.

## Workspaces And Persistence

Without `--workspace`, the workspace is `<state-root>/<name>/files`. A supplied
workspace is mounted at `/workspace`.

Add and remove extra directory mounts by alias:

```bash
aisbox mount -n demo1 /path/to/dir dir
aisbox unmount -n demo1 dir
```

The workspace and additional mounts are writable. Additional mounts appear at
`/workspace/<alias>` and expose the selected host directory to the agent. With
Docker's default outbound network access, agents can send mounted or supplied
data over the network; mount only trusted, necessary data.

Agent configuration persists under `<state-root>/<name>/config`. Runtime
containers use `docker run --rm` and are removed after the container exits.

## Commands

```bash
aisbox create -n demo1 -a claude
aisbox list
aisbox inspect -n demo1
aisbox mount -n demo1 /path/to/dir dir
aisbox unmount -n demo1 dir
aisbox env set -n demo1 KEY=VALUE
aisbox env unset -n demo1 KEY
aisbox run -n demo1 -- "summarize this repository"
aisbox attach -n demo1
aisbox shell -n demo1
aisbox rebuild -n demo1
aisbox set default -n demo1
aisbox doctor
aisbox delete -n demo1 --force
```

Run `aisbox --help` or `aisbox <command> --help` for current option details.

## Known Preview Limitations

- Only Claude Code and Codex CLI are supported.
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
