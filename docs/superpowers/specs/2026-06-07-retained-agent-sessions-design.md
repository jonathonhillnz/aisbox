# Retained Agent Sessions Design

## Summary

`aisbox` currently starts a fresh disposable container for every `run`,
`attach`, and `shell` invocation. This change renames the current interactive
agent command from `attach` to `start` and introduces retained agent sessions
that users can detach from and reattach to later.

Disposable execution remains the default and recommended workflow:

- `aisbox run` runs a non-interactive prompt in a disposable container.
- `aisbox start` runs an interactive agent in a disposable container.
- `aisbox shell` runs an interactive shell in a disposable container.

Retained sessions are an explicit option:

- `aisbox start --keep` starts or joins a retained interactive agent session.
- `aisbox attach` joins a retained session, starting one when necessary.
- `aisbox sessions` lists retained sessions.
- `aisbox kill` stops and removes a retained session.

Each environment can have at most one retained session.

## Command Behavior

### `aisbox start`

`aisbox start [-n NAME]` replaces the old `aisbox attach` behavior. It starts
the configured agent interactively in a fresh `docker run --rm` container.
When the agent exits, Docker removes the container.

`aisbox start [-n NAME] --keep` ensures that the environment has one running
retained container and attaches the terminal to it:

- If no retained container exists, it creates one and attaches immediately.
- If the retained container is running, it attaches to that container.
- If a stopped retained container exists, it removes the stopped container,
  creates a replacement, and attaches immediately.

Before creating or attaching to a retained session, the CLI prints:

```text
Detach without stopping: Ctrl-p Ctrl-q. Ctrl-c may stop the agent and session.
```

The rename is an intentional breaking change. There is no compatibility alias
for the old interactive meaning of `attach`.

### `aisbox attach`

`aisbox attach [-n NAME]` has the same retained-session resolution behavior as
`aisbox start --keep`:

- Attach to the running retained session when it exists.
- Remove and replace a stopped retained session.
- Start and attach to a retained session when none exists.

This makes `attach` convenient even when the user does not know whether a
retained session has already been created.

### `aisbox sessions`

`aisbox sessions` lists running retained sessions across all environments. Each
row includes:

- environment name
- configured agent
- Docker container name
- Docker status

When no retained sessions are running, it prints:

```text
No retained sessions found
```

Stopped retained containers are not listed as sessions. They are cleaned up
when the user next invokes `start --keep`, `attach`, or `kill` for that
environment.

### `aisbox kill`

`aisbox kill [-n NAME]` force-removes the environment's retained container.
Docker stops a running container as part of the removal. A stopped retained
container is also removed.

When no retained container exists, the command returns a concise user-facing
error without a traceback.

### Environment Selection

`start`, `attach`, and `kill` use the existing environment selection rules:
an explicit `-n/--name` overrides the configured default environment, and the
command errors when neither is available. `sessions` lists all retained
sessions and does not accept an environment selector.

## Docker Identity and Ownership

Docker is the source of truth for retained-session state. Session identifiers
are not persisted in `environment.json` or in a separate aisbox registry.

Each retained container has:

- deterministic name `aisbox-<environment-name>`
- label `dev.aisbox.managed=true`
- label `dev.aisbox.environment=<environment-name>`
- label `dev.aisbox.agent=<agent-name>`

The deterministic name supports direct lifecycle operations. Labels identify
ownership and provide structured fields for listing sessions.

Before operating on a deterministic container name, aisbox inspects it and
verifies the managed and environment labels. If an unrelated container already
uses the name, aisbox fails without attaching to, stopping, or removing that
container.

Session listing queries Docker by the managed label and still validates the
returned label data. Containers whose environment no longer exists in aisbox
state are omitted rather than presented as usable sessions.

## Container Construction

Disposable and retained containers share one construction path for:

- stored environment image
- `/workspace` working directory
- workspace bind mount
- agent configuration bind mount
- additional configured mounts
- stored environment variables
- configured agent interactive command

Disposable `run`, `start`, and `shell` containers include `--rm`. Retained
containers omit `--rm` and add the deterministic name and ownership labels.

Interactive creation uses `docker run -it`. Joining an existing running
session uses `docker attach`. Retained containers continue running only when
the user detaches with Docker's detach sequence and the agent process remains
alive. If the agent exits, the container becomes stopped and is replaced on
the next retained start or attach.

The feature does not add automatic restart policies, detached background
startup, multiple sessions per environment, or retained shells.

## Lifecycle and Stored Configuration

A retained container captures mounts, environment variables, image, and agent
configuration when it is created. Later mutations to the stored environment
do not alter an already-running container. Users must run `aisbox kill` and
then `aisbox attach` or `aisbox start --keep` to create a session with updated
configuration.

`aisbox rebuild` continues to rebuild and store the selected image but does
not replace a running retained container.

`aisbox delete` refuses to delete an environment while its retained container
exists, whether running or stopped. The error instructs the user to run:

```text
aisbox kill -n <environment>
```

This prevents environment state and bind-mounted managed files from being
deleted while the container still refers to them.

## Error Handling

Docker executable and subprocess failures are translated to `AisboxError`
messages and do not emit tracebacks for expected failures.

Specific safe failure cases include:

- deterministic name owned by a non-aisbox container
- retained container labels do not match the requested environment
- missing retained container for `kill`
- Docker attach, inspect, list, run, or remove failure
- environment deletion while a retained container exists

Race conditions between inspection and a Docker operation are reported as
normal Docker lifecycle failures. The command may be retried; aisbox never
falls back to operating on an unverified container.

## Testing

Docker subprocess calls remain mocked in the normal pytest suite. Coverage
includes:

- `start` replacing the old disposable interactive `attach`
- plain `start`, `run`, and `shell` retaining `docker run --rm`
- retained creation omitting `--rm` and including name and labels
- retained creation using the same mounts, environment, image, working
  directory, and interactive agent command
- `start --keep` and `attach` creating a missing retained session
- `start --keep` and `attach` joining a running retained session
- stopped retained-session removal and replacement
- detach guidance before retained creation or attachment
- session listing fields, filtering, and empty output
- running and stopped retained-session removal through `kill`
- clean errors when `kill` finds no retained container
- ownership validation and unrelated name-collision safety
- deletion protection for running and stopped retained containers
- default and explicit environment selection
- expected Docker failures producing no traceback
- CLI help, command documentation, and repository documentation checks

## Documentation

`README.md` will describe `run` and plain `start` as the normal disposable
workflows. It will document retained sessions as an explicit option, including
the `Ctrl-p Ctrl-q` Docker detach sequence and the warning that `Ctrl-c` may
stop the agent and session.

Examples and command references will replace the old interactive
`aisbox attach` usage with `aisbox start`, then separately demonstrate
`start --keep`, `attach`, `sessions`, and `kill`.

The safety model will be updated to distinguish disposable runtime containers
from explicitly retained session containers. Host agent configuration remains
unmounted, Docker continues to run as the current user without automatic
`sudo`, and persistence continues to come from explicit bind mounts and stored
environment configuration.
