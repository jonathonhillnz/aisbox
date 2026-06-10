from __future__ import annotations

import json
import os
import subprocess
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from aisbox.errors import AisboxError
from aisbox.models import AgentDefinition, DockerContainer, Environment, PermissionPolicy


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
        container_id=details["Id"],
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


def attach_container(container_id: str, runner: Runner = default_runner) -> None:
    runner(["docker", "attach", container_id], check=True)


def remove_container(container_id: str, runner: Runner = default_runner) -> None:
    runner(["docker", "rm", "--force", container_id], check=True)


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


@contextmanager
def _env_file_for(env: dict[str, str]) -> Iterator[str | None]:
    """Write env vars to a temp file and yield the path.

    The file is created with 0600 permissions and deleted on context exit.
    Yields ``None`` when *env* is empty (no temp file is created).
    """
    if not env:
        yield None
        return

    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            prefix="aisbox-env-",
        )
        os.chmod(tmp.name, 0o600)
        for key in sorted(env):
            tmp.write(f"{key}={env[key]}\n")
        tmp.close()
        yield tmp.name
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp.name)
            except FileNotFoundError:
                pass


def container_command(
    env: Environment,
    agent: AgentDefinition,
    config_source: str,
    mode: str,
    prompt: str | None = None,
    retained: bool = False,
    permission_policy: PermissionPolicy = "default",
    env_file: str | None = None,
) -> list[str]:
    if retained and mode != "start":
        raise ValueError("Retained containers require start mode")

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
    if env.env:
        if env_file is not None:
            command.extend(["--env-file", env_file])
        else:
            for key, value in sorted(env.env.items()):
                command.extend(["-e", f"{key}={value}"])
    command.append(env.image)
    if mode == "run":
        try:
            run_command = agent.run_permission_commands[permission_policy]
        except KeyError as exc:
            raise AisboxError(
                f"Permission policy '{permission_policy}' is not supported "
                f"for agent: {agent.name}"
            ) from exc
        command.extend(run_command)
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
    permission_policy: PermissionPolicy = "default",
) -> None:
    with _env_file_for(env.env) as env_file:
        runner(
            container_command(
                env,
                agent,
                config_source,
                mode,
                prompt,
                retained=retained,
                permission_policy=permission_policy,
                env_file=env_file,
            ),
            check=True,
        )
