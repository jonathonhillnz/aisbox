from __future__ import annotations

import subprocess
from collections.abc import Callable

from aienv.models import AgentDefinition


Runner = Callable[..., subprocess.CompletedProcess]


def default_runner(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, **kwargs)


def build_image(agent: AgentDefinition, runner: Runner = default_runner) -> None:
    runner(
        ["docker", "build", "-t", agent.image, "-"],
        input=agent.dockerfile,
        text=True,
        check=True,
    )


def docker_available(runner: Runner = default_runner) -> bool:
    try:
        runner(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    return True
