# aienv Design

## Goal

`aienv` is a command line wrapper for running AI coding agents such as Claude and Codex inside isolated Docker sandboxes. Each named environment has its own persisted config and workspace data under `~/.aienv`, and it never reads or copies the user's host `~/.claude` or `~/.codex` directories.

## Command Surface

Version 1 provides these commands:

```bash
aienv create -n demo1 -a claude -e ENVVAR1=bar -e ENVVAR2=foo
aienv create -n demo1 -a codex --workspace /path/to/source
aienv run -n demo1 -- "prompt text"
aienv attach -n demo1
aienv shell -n demo1
aienv delete -n demo1
aienv list
aienv inspect -n demo1
aienv rebuild -n demo1
aienv mount -n demo1 /path/to/dir dir
aienv unmount -n demo1 dir
aienv env set -n demo1 KEY=VALUE
aienv env unset -n demo1 KEY
aienv doctor
```

`create` creates a named environment, selects the AI agent, records environment variables, creates persistent directories, and builds the required local Docker image. `run` performs a non-interactive prompt run. `attach` starts an interactive TTY session for login, setup, or hands-on use. `shell` starts an interactive shell in the same sandbox shape without launching the agent. `delete` removes an environment. `list` shows known environments. `inspect` prints one environment's stored configuration. `rebuild` rebuilds the local image for an environment's selected agent. `mount` adds an extra host directory bind mount under the environment workspace. `unmount` removes an extra bind mount by alias. `env set` and `env unset` mutate stored environment variables after creation. `doctor` checks local prerequisites and summarizes problems.

## State Layout

Each environment lives under:

```text
~/.aienv/<name>/
  environment.json
  config/
    claude/
    codex/
  files/
```

`environment.json` stores:

```json
{
  "name": "demo1",
  "agent": "claude",
  "env": {
    "ENVVAR1": "bar",
    "ENVVAR2": "foo"
  },
  "workspace": "/home/user/.aienv/demo1/files",
  "mounts": [
    {
      "source": "/absolute/source/path",
      "alias": "dir"
    }
  ],
  "image": "aienv/claude:latest",
  "created_at": "2026-06-05T00:00:00Z"
}
```

If `--workspace` is not provided, the workspace is `~/.aienv/<name>/files`. If `--workspace` is provided, the resolved host path is stored and mounted at `/workspace`. The `files/` directory is still created as the default environment-owned workspace location.

Config is isolated per environment and per agent. Host config directories are not copied or mounted. Authentication can happen interactively inside `aienv attach`, or through explicit environment variables supplied at create time.

## Docker Images

`aienv` builds and manages local Docker images itself. Version 1 supports `claude` and `codex` agent definitions. Each agent definition specifies:

- agent name
- Dockerfile template
- non-interactive run command
- interactive attach command
- default shell command
- config mount path inside the container
- image tag

Image tags are deterministic:

```text
aienv/claude:latest
aienv/codex:latest
```

The base image should be debuggable and conservative, likely Debian or Ubuntu slim with common tools and Node/npm where needed by the current agent CLIs. The exact package install commands belong in the implementation plan and agent definitions, not in the state file.

## Runtime Behavior

`run`, `attach`, and `shell` create fresh containers using `docker run --rm`. Containers are disposable; persistence comes only from bind mounts. `aienv` invokes `docker` as the current user and does not automatically prefix Docker commands with `sudo`; users must have Docker access through their local Docker setup, the `docker` group, or rootless Docker.

Standard mounts:

```text
~/.aienv/<name>/config/<agent> -> agent-specific config path in the container
workspace path -> /workspace
```

Extra mounts:

```text
<host source> -> /workspace/<alias>
```

Environment variables stored during `create -e KEY=VALUE` are passed to every container for that environment.

`run` passes the provided prompt to the agent command and exits with the same status as the agent process. `attach` allocates an interactive TTY and starts the agent's interactive command. It is suitable for first-run authentication and normal interactive work. `shell` allocates an interactive TTY and starts the configured shell command, usually `/bin/bash`, with the same mounts, working directory, and environment variables as agent runs.

`rebuild` runs the image build for the environment's selected agent again and updates the stored image tag if the agent definition changes. It does not change workspace files, config files, env vars, or mounts.

`doctor` checks Docker availability, Docker daemon reachability, Docker permission for the current user, whether `~/.aienv` can be created and written, whether supported agent definitions are available, and whether known local images exist. It returns a non-zero status when required prerequisites are missing.

## Validation And Safety

Environment names must match:

```text
[a-zA-Z0-9_.-]+
```

`create` fails if the environment already exists. `delete` asks for confirmation unless `--force` is supplied. `mount` requires an existing host directory, stores the resolved absolute source path, and rejects aliases that are absolute, empty, contain `/`, or contain `..`. `mount` fails if the alias already exists. `unmount` fails if the alias does not exist. `env set` requires `KEY=VALUE` and overwrites existing keys. `env unset` fails if the key is not currently stored.

The CLI fails early with clear messages when:

- Docker is missing, not reachable, or not usable by the current user
- the requested agent is unsupported
- an environment name does not exist
- an environment variable is not `KEY=VALUE`
- a workspace or mount path does not exist
- an image build fails
- a mount alias already exists or cannot be found
- an environment variable cannot be found for `env unset`

All workspace and extra mounts are read/write in version 1 because the agents need to edit files. Read-only mounts are out of scope for version 1.

## Packaging

`aienv` is a Python CLI package. Initial installation is from the repository with:

```bash
pipx install .
```

The project uses `pyproject.toml` with a console script entrypoint named `aienv`. The package structure should remain compatible with a future PyPI release and Homebrew formula, but neither publishing path is part of version 1.

## Testing

Tests avoid requiring real Claude or Codex credentials.

Unit tests cover:

- name, environment variable, and mount alias validation
- environment JSON creation, loading, listing, and deletion
- Docker build and run command construction
- agent definition lookup
- env var mutation with `env set` and `env unset`
- mount removal with `unmount`
- `inspect` output formatting
- `doctor` prerequisite checks
- CLI error messages for common failures

Integration-style tests use mocked subprocess calls to verify:

- `create` calls Docker image build
- `rebuild` calls Docker image build for the stored agent
- `run`, `attach`, and `shell` produce the expected Docker arguments
- environment variables are passed into containers
- extra mounts are persisted and included in container runs

## Out Of Scope For Version 1

- copying host credentials
- sharing host `~/.claude` or `~/.codex`
- long-running reusable containers
- GUI apps
- remote Docker hosts
- automatic `sudo` elevation for Docker
- read-only mounts
- multiple simultaneous workspaces per environment
- shell completion
- Homebrew formula
- PyPI publishing
