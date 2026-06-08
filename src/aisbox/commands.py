from __future__ import annotations

import fcntl
import json
import os
import stat
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from aisbox.agents import get_agent, supported_agents
from aisbox.docker import (
    AGENT_LABEL,
    ENVIRONMENT_LABEL,
    MANAGED_LABEL,
    attach_container,
    build_image,
    docker_available,
    inspect_container,
    list_retained_containers,
    remove_container,
    retained_container_name,
    run_container,
)
from aisbox.errors import AisboxError
from aisbox.models import DockerContainer, Environment, Mount, RetainedSession
from aisbox.store import EnvironmentStore
from aisbox.validation import (
    parse_env_assignment,
    validate_env_key,
    validate_env_name,
    validate_mount_alias,
)

_LIFECYCLE_LOCK_NAMESPACE = "@locks"


def create_environment(
    name: str,
    agent_name: str,
    env_assignments: list[str],
    workspace: str | None,
    store: EnvironmentStore | None = None,
) -> Environment:
    store = store or EnvironmentStore()
    name = validate_env_name(name)
    if store.exists(name):
        raise AisboxError(f"Environment already exists: {name}")
    agent = get_agent(agent_name)
    env = dict(parse_env_assignment(item) for item in env_assignments)
    store.create_dirs(name, agent.name)
    workspace_path = Path(workspace).expanduser().resolve() if workspace else store.default_workspace(name)
    if not workspace_path.exists() or not workspace_path.is_dir():
        raise AisboxError(f"Workspace path does not exist: {workspace_path}")
    created = Environment(
        name=name,
        agent=agent.name,
        env=env,
        workspace=str(workspace_path),
        mounts=[],
        image=agent.image,
        created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    try:
        build_image(agent)
    except FileNotFoundError as exc:
        raise AisboxError("Docker is not installed or not available on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise AisboxError(f"Docker image build failed for agent: {agent.name}") from exc
    store.save(created)
    return created


def list_environments(store: EnvironmentStore | None = None) -> list[Environment]:
    return (store or EnvironmentStore()).list()


def inspect_environment(name: str, store: EnvironmentStore | None = None) -> Environment:
    return (store or EnvironmentStore()).load(name)


def delete_environment(name: str, store: EnvironmentStore | None = None) -> None:
    store = store or EnvironmentStore()
    with _lifecycle_lock(
        name,
        store,
        include_kill_guidance=True,
    ) as validated_name:
        env = store.load(validated_name)
        try:
            container = _inspect_retained(env)
        except FileNotFoundError as exc:
            raise AisboxError(
                "Docker is not installed or not available on PATH"
            ) from exc
        except (
            subprocess.CalledProcessError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
        ) as exc:
            raise _docker_failure("container inspection", env.name) from exc
        if container is not None:
            raise AisboxError(
                f"Environment {validated_name} has a retained session; "
                f"run 'aisbox kill -n {validated_name}' first"
            )
        store.delete(validated_name)


def set_default_environment(name: str, store: EnvironmentStore | None = None) -> str:
    store = store or EnvironmentStore()
    name = validate_env_name(name)
    store.set_default_environment(name)
    return name


def resolve_environment_name(
    name: str | None,
    store: EnvironmentStore | None = None,
) -> str:
    store = store or EnvironmentStore()
    if name is not None:
        return validate_env_name(name)
    default_name = store.load_default_environment()
    if default_name is None:
        raise AisboxError("No environment specified and no default environment is set")
    return default_name


def add_mount(
    name: str,
    source: str,
    alias: str,
    store: EnvironmentStore | None = None,
) -> Mount:
    store = store or EnvironmentStore()
    env = store.load(name)
    alias = validate_mount_alias(alias)
    source_path = Path(source).expanduser().resolve()
    if not source_path.exists() or not source_path.is_dir():
        raise AisboxError(f"Mount source path must be an existing directory: {source_path}")
    if any(mount.alias == alias for mount in env.mounts):
        raise AisboxError(f"Mount alias already exists: {alias}")
    mount = Mount(source=str(source_path), alias=alias)
    env.mounts.append(mount)
    store.save(env)
    return mount


def remove_mount(name: str, alias: str, store: EnvironmentStore | None = None) -> None:
    store = store or EnvironmentStore()
    env = store.load(name)
    alias = validate_mount_alias(alias)
    original_count = len(env.mounts)
    env.mounts = [mount for mount in env.mounts if mount.alias != alias]
    if len(env.mounts) == original_count:
        raise AisboxError(f"Mount alias does not exist: {alias}")
    store.save(env)


def _runtime_environment(
    env: Environment,
    workspace: str | None = None,
    mounts: list[tuple[str, str]] | None = None,
) -> Environment:
    runtime_workspace = env.workspace
    if workspace is not None:
        workspace_path = Path(workspace).expanduser().resolve()
        if not workspace_path.exists() or not workspace_path.is_dir():
            raise AisboxError(
                f"Workspace path does not exist: {workspace_path}"
            )
        runtime_workspace = str(workspace_path)

    runtime_mounts = list(env.mounts)
    seen_aliases = {mount.alias for mount in runtime_mounts}
    for source, alias_value in mounts or []:
        alias = validate_mount_alias(alias_value)
        if alias in seen_aliases:
            raise AisboxError(f"Mount alias already exists: {alias}")
        source_path = Path(source).expanduser().resolve()
        if not source_path.exists() or not source_path.is_dir():
            raise AisboxError(
                f"Mount source path must be an existing directory: {source_path}"
            )
        runtime_mounts.append(Mount(source=str(source_path), alias=alias))
        seen_aliases.add(alias)

    return Environment(
        name=env.name,
        agent=env.agent,
        env=dict(env.env),
        workspace=runtime_workspace,
        mounts=runtime_mounts,
        image=env.image,
        created_at=env.created_at,
    )


def set_env_vars(
    name: str,
    assignments: list[str],
    store: EnvironmentStore | None = None,
) -> list[str]:
    parsed = [parse_env_assignment(assignment) for assignment in assignments]
    store = store or EnvironmentStore()
    env = store.load(name)
    for key, value in parsed:
        env.env[key] = value
    store.save(env)
    return [key for key, _ in parsed]


def unset_env_vars(
    name: str,
    keys: list[str],
    store: EnvironmentStore | None = None,
) -> list[str]:
    validated = [validate_env_key(key) for key in keys]
    if len(validated) != len(set(validated)):
        raise AisboxError("Environment variable keys must not be repeated")
    store = store or EnvironmentStore()
    env = store.load(name)
    for key in validated:
        if key not in env.env:
            raise AisboxError(f"Environment variable is not set: {key}")
    for key in validated:
        del env.env[key]
    store.save(env)
    return validated


def run_environment(
    name: str,
    mode: str,
    prompt: str | None = None,
    store: EnvironmentStore | None = None,
    *,
    workspace: str | None = None,
    mounts: list[tuple[str, str]] | None = None,
) -> None:
    store = store or EnvironmentStore()
    env = _runtime_environment(store.load(name), workspace, mounts)
    agent = get_agent(env.agent)
    config_source = str(store.config_dir(env.name))
    try:
        run_container(env, agent, config_source, mode, prompt)
    except FileNotFoundError as exc:
        raise AisboxError("Docker is not installed or not available on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise AisboxError(f"Docker container failed for environment: {env.name}") from exc


def _docker_failure(action: str, environment: str | None = None) -> AisboxError:
    suffix = f" for environment: {environment}" if environment else ""
    return AisboxError(f"Docker {action} failed{suffix}")


@contextmanager
def _lifecycle_lock(
    name: str,
    store: EnvironmentStore,
    *,
    include_kill_guidance: bool = False,
) -> Iterator[str]:
    name = validate_env_name(name)
    lock_dir = store.root / _LIFECYCLE_LOCK_NAMESPACE
    directory_fd: int | None = None
    lock_fd: int | None = None
    acquired = False
    try:
        try:
            store.ensure_root()
            previous_umask = os.umask(0)
            try:
                try:
                    lock_dir.mkdir(mode=0o700)
                except FileExistsError:
                    pass
            finally:
                os.umask(previous_umask)

            directory_fd = os.open(
                lock_dir,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
            )
            if not stat.S_ISDIR(os.fstat(directory_fd).st_mode):
                raise OSError("Lifecycle lock path is not a directory")
            os.fchmod(directory_fd, 0o700)

            lock_fd = os.open(
                f"{name}.lock",
                os.O_RDWR
                | os.O_CREAT
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_NONBLOCK", 0),
                0o600,
                dir_fd=directory_fd,
            )
            if not stat.S_ISREG(os.fstat(lock_fd).st_mode):
                raise OSError("Lifecycle lock path is not a regular file")
            os.fchmod(lock_fd, 0o600)
        except (AisboxError, OSError) as exc:
            raise AisboxError(
                f"Lifecycle lock could not be acquired for environment: {name}"
            ) from exc

        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except BlockingIOError as exc:
            guidance = (
                f"; run 'aisbox kill -n {name}' and retry"
                if include_kill_guidance
                else ""
            )
            raise AisboxError(
                f"Another lifecycle operation is active for environment: "
                f"{name}{guidance}"
            ) from exc
        except OSError as exc:
            raise AisboxError(
                f"Lifecycle lock could not be acquired for environment: {name}"
            ) from exc

        yield name
    finally:
        if lock_fd is not None:
            if acquired:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                except OSError:
                    pass
            os.close(lock_fd)
        if directory_fd is not None:
            os.close(directory_fd)


def _owned_retained_container(
    env: Environment,
    container: DockerContainer | None,
) -> DockerContainer | None:
    if container is None:
        return None
    expected_labels = {
        MANAGED_LABEL: "true",
        ENVIRONMENT_LABEL: env.name,
        AGENT_LABEL: env.agent,
    }
    if (
        container.name != retained_container_name(env.name)
        or any(
            container.labels.get(key) != value
            for key, value in expected_labels.items()
        )
    ):
        raise AisboxError(
            f"Container name {container.name} is not managed by aisbox "
            f"for environment: {env.name}"
        )
    return container


def _inspect_retained(env: Environment) -> DockerContainer | None:
    return _owned_retained_container(
        env,
        inspect_container(retained_container_name(env.name)),
    )


def _has_runtime_overrides(
    workspace: str | None,
    mounts: list[tuple[str, str]] | None,
) -> bool:
    return workspace is not None or bool(mounts)


def _run_retained(
    env: Environment,
    store: EnvironmentStore,
    *,
    workspace: str | None = None,
    mounts: list[tuple[str, str]] | None = None,
) -> None:
    runtime_env = _runtime_environment(env, workspace, mounts)
    agent = get_agent(env.agent)
    run_container(
        runtime_env,
        agent,
        str(store.config_dir(env.name)),
        "start",
        retained=True,
    )


def _ensure_retained_session(
    name: str,
    store: EnvironmentStore | None = None,
    *,
    workspace: str | None = None,
    mounts: list[tuple[str, str]] | None = None,
) -> None:
    store = store or EnvironmentStore()
    with _lifecycle_lock(name, store) as validated_name:
        env = store.load(validated_name)
        try:
            container = _inspect_retained(env)
            if container is None:
                _run_retained(env, store, workspace=workspace, mounts=mounts)
            elif container.status == "running":
                if _has_runtime_overrides(workspace, mounts):
                    raise AisboxError(
                        f"Environment {env.name} already has a retained session; "
                        f"run 'aisbox kill -n {env.name}' before starting one "
                        "with different mounts"
                    )
                attach_container(container.container_id)
            else:
                remove_container(container.container_id)
                _run_retained(env, store, workspace=workspace, mounts=mounts)
        except AisboxError:
            raise
        except FileNotFoundError as exc:
            raise AisboxError(
                "Docker is not installed or not available on PATH"
            ) from exc
        except (
            subprocess.CalledProcessError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
        ) as exc:
            raise _docker_failure("retained session operation", env.name) from exc


def start_environment(
    name: str,
    keep: bool,
    store: EnvironmentStore | None = None,
    *,
    workspace: str | None = None,
    mounts: list[tuple[str, str]] | None = None,
) -> None:
    if keep:
        _ensure_retained_session(name, store, workspace=workspace, mounts=mounts)
        return
    run_environment(name, "start", store=store, workspace=workspace, mounts=mounts)


def attach_environment(
    name: str,
    store: EnvironmentStore | None = None,
    *,
    workspace: str | None = None,
    mounts: list[tuple[str, str]] | None = None,
) -> None:
    _ensure_retained_session(name, store, workspace=workspace, mounts=mounts)


def list_sessions(
    store: EnvironmentStore | None = None,
) -> list[RetainedSession]:
    store = store or EnvironmentStore()
    try:
        containers = list_retained_containers()
    except FileNotFoundError as exc:
        raise AisboxError("Docker is not installed or not available on PATH") from exc
    except (
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as exc:
        raise _docker_failure("session listing") from exc

    sessions = []
    for container in containers:
        if container.status != "running":
            continue
        environment_name = container.labels.get(ENVIRONMENT_LABEL)
        agent_name = container.labels.get(AGENT_LABEL)
        if (
            container.labels.get(MANAGED_LABEL) != "true"
            or environment_name is None
            or agent_name is None
        ):
            continue
        try:
            if not store.exists(environment_name):
                continue
            env = store.load(environment_name)
        except AisboxError:
            continue
        if (
            env.agent != agent_name
            or container.name != retained_container_name(env.name)
        ):
            continue
        sessions.append(
            RetainedSession(
                environment=env.name,
                agent=env.agent,
                container=container.name,
                status=container.status,
            )
        )
    return sorted(sessions, key=lambda session: session.environment)


def kill_session(
    name: str,
    store: EnvironmentStore | None = None,
) -> None:
    store = store or EnvironmentStore()
    env = store.load(name)
    try:
        container = _inspect_retained(env)
        if container is None:
            raise AisboxError(f"No retained session exists for environment: {name}")
        remove_container(container.container_id)
    except AisboxError:
        raise
    except FileNotFoundError as exc:
        raise AisboxError("Docker is not installed or not available on PATH") from exc
    except (
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as exc:
        raise _docker_failure("container removal", env.name) from exc


def rebuild_environment(name: str, store: EnvironmentStore | None = None) -> None:
    store = store or EnvironmentStore()
    env = store.load(name)
    agent = get_agent(env.agent)
    try:
        build_image(agent)
    except FileNotFoundError as exc:
        raise AisboxError("Docker is not installed or not available on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise AisboxError(f"Docker image build failed for agent: {agent.name}") from exc
    env.image = agent.image
    store.save(env)


@dataclass(frozen=True)
class DoctorResult:
    ok: bool
    lines: list[str]


def doctor(store: EnvironmentStore | None = None) -> DoctorResult:
    store = store or EnvironmentStore()
    lines = []
    ok = True
    if docker_available():
        lines.append("Docker: ok")
    else:
        lines.append("Docker: missing, unreachable, or permission denied")
        ok = False
    try:
        store.ensure_root()
        probe_path: Path | None = None
        cleanup_error: OSError | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                delete=False,
                dir=store.root,
                prefix=".doctor-",
            ) as probe:
                probe_path = Path(probe.name)
                probe.write("ok\n")
        finally:
            if probe_path is not None:
                try:
                    probe_path.unlink(missing_ok=True)
                except OSError as exc:
                    cleanup_error = exc
        if cleanup_error is not None:
            raise cleanup_error
        lines.append("State directory: ok")
    except (AisboxError, OSError) as exc:
        lines.append(f"State directory: not writable: {store.root} ({exc})")
        ok = False
    lines.append("Supported agents: " + ", ".join(supported_agents()))
    return DoctorResult(ok=ok, lines=lines)
