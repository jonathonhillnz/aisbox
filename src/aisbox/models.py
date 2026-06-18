from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


PermissionPolicy = Literal["default", "auto", "bypass"]


@dataclass(frozen=True)
class Mount:
    source: str
    alias: str


@dataclass
class Environment:
    name: str
    agent: str
    env: dict[str, str]
    workspace: str
    mounts: list[Mount]
    image: str
    created_at: str


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    image: str
    config_path: str
    dockerfile: str
    run_command: list[str]
    run_permission_commands: dict[PermissionPolicy, list[str]]
    attach_command: list[str]
    start_permission_commands: dict[PermissionPolicy, list[str]] = field(
        default_factory=dict
    )
    shell_command: list[str] = field(default_factory=lambda: ["/bin/bash"])


@dataclass(frozen=True)
class DockerContainer:
    container_id: str
    name: str
    status: str
    labels: dict[str, str]


@dataclass(frozen=True)
class RetainedSession:
    environment: str
    agent: str
    container: str
    status: str
