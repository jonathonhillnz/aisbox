# Workspaces & Persistence

## Default managed workspace

Without `--workspace`, each environment gets a managed workspace at
`<state-root>/<name>/files`. This directory is created with mode `0700` and
mounted at `/workspace` inside the container.

## Supplying a workspace

Pass `--workspace` at creation to use an existing directory:

```bash
aisbox create -n <name> -a claude --workspace /path/to/source
```

The path must be an existing directory. It is mounted at `/workspace` inside
the container.

## Additional mounts

Add persistent mounts by alias with `aisbox mount`:

```bash
aisbox mount -n <name> /path/to/dir <alias>
```

The host directory is mounted at `/workspace/<alias>`. The source must be an
existing directory.

Remove a mount:

```bash
aisbox unmount -n <name> <alias>
```

Mounts are stored in the environment configuration and applied to every
container run.

!!! warning
    Workspaces and additional mounts are writable and exposed to the agent.
    With Docker's default outbound network access, agents can send mounted
    or supplied data over the network. Mount only trusted, necessary data.

## Temporary workspace and mount overrides

Override the workspace or add mounts for a single runtime session without
saving them to the environment:

```bash
aisbox run -n <name> --workspace /path/to/temp/workspace -- "prompt"
aisbox start -n <name> --workspace /path/to/temp/workspace
aisbox start -n <name> --mount /path/to/dir <alias>
aisbox attach -n <name> --mount /path/to/dir <alias>
```

Temporary mount aliases must not conflict with existing persistent mount
aliases.

### Lifetime of temporary overrides

- **Disposable `run` and plain `start`:** overrides apply to one container
  only. The container is removed on exit.
- **Retained sessions (`start --keep`, `attach`):** overrides last until the
  retained container created with those overrides is killed or replaced. When
  a retained session is already running, `attach` and `start --keep` with
  overrides fail because running container mounts cannot be changed.

## Agent configuration persistence

Agent configuration is persisted under `<state-root>/<name>/config`. This
directory is mounted into the container at the agent's config path
(`/home/aisbox` for all three agents). Configuration written by the agent
during a session survives container removal because it is stored on a bind
mount.

!!! note
    OpenCode may read project `CLAUDE.md` and `.claude/skills` files from the
    mounted workspace through its upstream compatibility behavior. aisbox does
    not copy or mount host `~/.claude` state.

## What persists and what does not

| What | Survives container removal? |
|------|----------------------------|
| Environment configuration (`environment.json`) | Yes — stored on host |
| Agent config directory (`<state-root>/<name>/config`) | Yes — bind mount |
| Managed workspace (`<state-root>/<name>/files`) | Yes — bind mount |
| Supplied workspace | Yes — bind mount to host directory |
| Additional mounts | Yes — bind mounts to host directories |
| Retained container writable layer | No — discarded on kill/replace |
| Disposable container (`--rm`) filesystem | No — removed on exit |
