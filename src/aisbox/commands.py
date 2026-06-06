from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from aisbox.agents import get_agent, supported_agents
from aisbox.docker import build_image, docker_available, run_container
from aisbox.errors import AisboxError
from aisbox.models import Environment, Mount
from aisbox.store import EnvironmentStore
from aisbox.validation import parse_env_assignment, validate_env_name, validate_mount_alias


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
    (store or EnvironmentStore()).delete(name)


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


def set_env_var(
    name: str,
    assignment: str,
    store: EnvironmentStore | None = None,
) -> str:
    store = store or EnvironmentStore()
    env = store.load(name)
    key, value = parse_env_assignment(assignment)
    env.env[key] = value
    store.save(env)
    return key


def unset_env_var(name: str, key: str, store: EnvironmentStore | None = None) -> None:
    store = store or EnvironmentStore()
    env = store.load(name)
    if key not in env.env:
        raise AisboxError(f"Environment variable is not set: {key}")
    del env.env[key]
    store.save(env)


def run_environment(
    name: str,
    mode: str,
    prompt: str | None = None,
    store: EnvironmentStore | None = None,
) -> None:
    store = store or EnvironmentStore()
    env = store.load(name)
    agent = get_agent(env.agent)
    config_source = str(store.config_dir(env.name))
    try:
        run_container(env, agent, config_source, mode, prompt)
    except FileNotFoundError as exc:
        raise AisboxError("Docker is not installed or not available on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise AisboxError(f"Docker container failed for environment: {env.name}") from exc


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
        store.root.mkdir(parents=True, exist_ok=True)
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
    except OSError as exc:
        lines.append(f"State directory: not writable: {store.root} ({exc})")
        ok = False
    lines.append("Supported agents: " + ", ".join(supported_agents()))
    return DoctorResult(ok=ok, lines=lines)
