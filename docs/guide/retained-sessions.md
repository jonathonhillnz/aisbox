# Retained Sessions

A retained session is an interactive agent container that persists across
detach and reconnect. It lets you leave a session running and return to it
later without losing the container state for the lifetime of that container.

## Starting a retained session

```bash
aisbox start -n <name> --keep
```

Only one retained container exists per environment at a time.

## Detaching

Press `Ctrl-p` followed by `Ctrl-q` in sequence. This detaches your terminal
from the container without stopping it. The agent and session continue
running.

`Ctrl-c` alone may stop the agent and the retained session instead of
detaching. Use `Ctrl-p Ctrl-q` to leave the session running.

## Reattaching

```bash
aisbox attach -n <name>
```

`aisbox attach` uses the one retained container for the environment. Its
behavior depends on the container state:

- **Running:** attaches to the existing container.
- **Missing:** creates a new retained container using the current environment
  configuration (mounts, environment variables, image).
- **Stopped:** removes the stopped container and creates a replacement using
  the current environment configuration.

!!! note
    When `attach` replaces a stopped container, the previous container's
    writable-layer filesystem state is discarded. The new container starts
    fresh with the environment's bind mounts and configuration.

## Listing retained sessions

```bash
aisbox sessions
```

Shows running retained sessions. If none are found, it prints
`No retained sessions found`.

## Killing a retained session

```bash
aisbox kill -n <name>
```

Stops and removes the retained container. The container's writable-layer
filesystem state is discarded.

## Applying configuration changes

The retained container captures the environment's mounts, environment
variables, and image when it is created. If you change the environment
configuration (add a mount, set an env var, rebuild the image), the running
retained container does not automatically pick up those changes.

To apply configuration changes, kill and recreate the session:

```bash
aisbox kill -n <name>
aisbox attach -n <name>
```

The next `attach` (or `start --keep`) creates a new retained container with
the current configuration.

## Temporary overrides with retained sessions

Temporary `--workspace` and `--mount` overrides can be used when creating a
retained session. They are not saved to the environment configuration and last
until the retained container is killed or replaced. If a retained session is
already running, `attach` and `start --keep` with overrides fail because
running container mounts cannot be changed.

## Writable-layer state is not durable

The retained container's writable-layer filesystem survives detach and
reconnect, but it is not durable persistence. The writable layer is discarded
when:

- You run `aisbox kill -n <name>`.
- `aisbox attach` replaces a stopped container.
- Docker itself removes the container.

**Durable persistence across container removal comes only from explicit bind
mounts and stored environment configuration.** Do not rely on the retained
container filesystem for data you need to keep.
