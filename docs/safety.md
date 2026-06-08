# Safety Model

`aisbox` reduces accidental host exposure by running agents inside Docker
containers with isolated filesystem, user, and configuration boundaries.
Docker is **not a complete security boundary** — review every workspace and
additional directory you mount.

This page describes the safety properties `aisbox` provides and the residual
risks you must manage.

## State root isolation

The configured state root (`<state-root>`) is `~/.aisbox` by default and is
overridden by the `AISBOX_HOME` environment variable. All environment
configuration, managed workspaces, agent config, and settings live under this
directory.

`aisbox` creates managed state directories with mode `0700` and managed state
files with mode `0600`, and tightens those permissions on subsequent writes.
Protect the state root as sensitive data — it contains unencrypted
credentials.

## Host configuration not shared

Host `~/.claude`, `~/.codex`, and OpenCode user configuration and credential
directories are **not** copied or mounted into containers. Each agent starts
with its own configuration directory under `<state-root>/<name>/config`.

!!! note
    OpenCode may read project `CLAUDE.md` and `.claude/skills` files from the
    mounted workspace through its upstream compatibility behavior. These are
    project files within your workspace, not host-level configuration.

## Docker runs as the current user

`aisbox` invokes Docker as the current user without `sudo`. Container
processes run as a non-root `aisbox` user inside the container. This avoids
running containers as root.

## Container lifecycle

- **Disposable by default:** `aisbox run`, plain `aisbox start`, and
  `aisbox shell` use `docker run --rm`. Containers are removed when they exit.
- **Retained sessions are opt-in:** `aisbox start --keep` and `aisbox attach`
  explicitly retain one interactive container per environment. The retained
  container persists until `aisbox kill`.

A retained container's writable-layer filesystem may contain sensitive data
and is discarded when the container is removed. Durable persistence across
container removal comes only from explicit bind mounts and stored environment
configuration.

## Network access

Containers use Docker's default outbound network access. Agents can send
mounted or supplied data over the network. **Mount only trusted, necessary
data.** Assume any data accessible inside the container can be exfiltrated by
the agent.

## Credential storage

Environment variable values are stored unencrypted in
`<state-root>/<name>/environment.json`. The restrictive managed-state
permissions (`0700` directories, `0600` files) reduce local exposure, but
anyone with read access to the state root can read the credentials.

`aisbox inspect` masks stored values, showing only `<set>` for each key.

!!! warning
    Explicit non-empty values passed on the command line with `-e KEY=VALUE`
    may remain in shell history and, depending on the host, may be observable
    to local processes or users. Prefer the hidden-prompt flow (`-e KEY=`)
    or interactive authentication inside the container for secrets.

## Mount safety

- Workspaces and additional mounts are writable.
- Agents have read/write access to `/workspace` and all mount aliases.
- Mount only directories you trust the agent to read and modify.

## What aisbox does not provide

- **No VM-level isolation.** The boundary is Linux namespaces via Docker, not
  gVisor, Firecracker, or a virtual machine.
- **No network restrictions.** Containers have default Docker outbound
  network access.
- **No resource limits.** CPU and memory are not constrained by aisbox.
- **No encryption at rest** for stored credentials.

## Reporting vulnerabilities

Report suspected vulnerabilities according to
[SECURITY.md](https://github.com/jonathonhillnz/aisbox/blob/main/SECURITY.md).
Do not open a public issue or disclose the report through other public
channels.

Acknowledgement, investigation, and remediation are best-effort during the
public preview.
