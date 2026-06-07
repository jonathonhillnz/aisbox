from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable

from aisbox.models import AgentDefinition, DockerContainer, Environment


Runner = Callable[..., subprocess.CompletedProcess]

MANAGED_LABEL = "dev.aisbox.managed"
ENVIRONMENT_LABEL = "dev.aisbox.environment"
AGENT_LABEL = "dev.aisbox.agent"


def default_runner(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, **kwargs)


def retained_container_name(environment_name: str) -> str:
    return f"aisbox-{environment_name}"


def inspect_container(
    name: str,
    runner: Runner = default_runner,
) -> DockerContainer | None:
    result = runner(
        [
            "docker",
            "container",
            "inspect",
            "--format",
            "{{json .}}",
            name,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        if "No such container" in result.stderr or "No such object" in result.stderr:
            return None
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )

    details = json.loads(result.stdout)
    return DockerContainer(
        name=details["Name"].removeprefix("/"),
        status=details["State"]["Status"],
        labels=details["Config"]["Labels"] or {},
    )


def list_retained_containers(
    runner: Runner = default_runner,
) -> list[DockerContainer]:
    result = runner(
        [
            "docker",
            "ps",
            "--all",
            "--filter",
            f"label={MANAGED_LABEL}=true",
            "--format",
            "{{.Names}}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    containers = []
    for line in result.stdout.splitlines():
        name = line.strip()
        if not name:
            continue
        container = inspect_container(name, runner=runner)
        if container is not None:
            containers.append(container)
    return containers


def attach_container(name: str, runner: Runner = default_runner) -> None:
    runner(["docker", "attach", name], check=True)


def remove_container(name: str, runner: Runner = default_runner) -> None:
    runner(["docker", "rm", "--force", name], check=True)


def build_image(agent: AgentDefinition, runner: Runner = default_runner) -> None:
    runner(
        [
            "docker",
            "build",
            "-t",
            agent.image,
            "--build-arg",
            f"AISBOX_UID={os.getuid()}",
            "--build-arg",
            f"AISBOX_GID={os.getgid()}",
            "-",
        ],
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
    retained: bool = False,
) -> list[str]:
    if retained and mode != "start":
        raise ValueError("Retained containers require start mode")
    # Remove this alias when the CLI attach command is migrated to start.
    if mode == "attach":
        mode = "start"

    command = ["docker", "run"]
    if retained:
        command.extend(["--name", retained_container_name(env.name)])
        command.extend(["--label", f"{MANAGED_LABEL}=true"])
        command.extend(["--label", f"{ENVIRONMENT_LABEL}={env.name}"])
        command.extend(["--label", f"{AGENT_LABEL}={agent.name}"])
    else:
        command.append("--rm")
    command.extend(["-w", "/workspace"])
    if mode in {"start", "shell"}:
        command.extend(["-it"])
    command.extend(["-v", f"{env.workspace}:/workspace"])
    command.extend(["-v", f"{config_source}:{agent.config_path}"])
    for mount in env.mounts:
        command.extend(["-v", f"{mount.source}:/workspace/{mount.alias}"])
    for key, value in sorted(env.env.items()):
        command.extend(["-e", f"{key}={value}"])
    command.append(env.image)
    if mode == "run":
        command.extend(agent.run_command)
        if prompt is not None:
            command.append(prompt)
    elif mode == "start":
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
    *,
    retained: bool = False,
) -> None:
    runner(
        container_command(
            env,
            agent,
            config_source,
            mode,
            prompt,
            retained=retained,
        ),
        check=True,
    )
