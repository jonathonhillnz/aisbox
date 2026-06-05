from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from aienv.agents import get_agent
from aienv.docker import build_image
from aienv.errors import AienvError
from aienv.models import Environment
from aienv.store import EnvironmentStore
from aienv.validation import parse_env_assignment, validate_env_name


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
        raise AienvError(f"Environment already exists: {name}")
    agent = get_agent(agent_name)
    env = dict(parse_env_assignment(item) for item in env_assignments)
    store.create_dirs(name, agent.name)
    workspace_path = Path(workspace).expanduser().resolve() if workspace else store.default_workspace(name)
    if not workspace_path.exists() or not workspace_path.is_dir():
        raise AienvError(f"Workspace path does not exist: {workspace_path}")
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
        raise AienvError("Docker is not installed or not available on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise AienvError(f"Docker image build failed for agent: {agent.name}") from exc
    store.save(created)
    return created


def list_environments(store: EnvironmentStore | None = None) -> list[Environment]:
    return (store or EnvironmentStore()).list()


def inspect_environment(name: str, store: EnvironmentStore | None = None) -> Environment:
    return (store or EnvironmentStore()).load(name)


def delete_environment(name: str, store: EnvironmentStore | None = None) -> None:
    (store or EnvironmentStore()).delete(name)
