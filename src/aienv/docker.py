from __future__ import annotations

import subprocess
from collections.abc import Callable

from aienv.models import AgentDefinition, Environment


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


def container_command(
    env: Environment,
    agent: AgentDefinition,
    config_source: str,
    mode: str,
    prompt: str | None = None,
) -> list[str]:
    command = ["docker", "run", "--rm", "-w", "/workspace"]
    if mode in {"attach", "shell"}:
        command.extend(["-it"])
    command.extend(["-v", f"{env.workspace}:/workspace"])
    command.extend(["-v", f"{config_source}:{agent.config_path}"])
    for mount in env.mounts:
        command.extend(["-v", f"{mount.source}:/workspace/{mount.alias}"])
    for key, value in sorted(env.env.items()):
        command.extend(["-e", f"{key}={value}"])
    command.append(agent.image)
    if mode == "run":
        command.extend(agent.run_command)
        if prompt is not None:
            command.append(prompt)
    elif mode == "attach":
        command.extend(agent.attach_command)
    elif mode == "shell":
        command.extend(agent.shell_command)
    else:
        raise ValueError(f"Unknown container mode: {mode}")
    return command


def run_container(
    env: Environment,
    agent: AgentDefinition,
    config_source: str,
    mode: str,
    prompt: str | None = None,
    runner: Runner = default_runner,
) -> None:
    runner(container_command(env, agent, config_source, mode, prompt), check=True)
