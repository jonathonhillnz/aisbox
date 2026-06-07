import subprocess
from unittest.mock import Mock

import pytest

from aisbox.agents import get_agent
from aisbox.docker import (
    AGENT_LABEL,
    ENVIRONMENT_LABEL,
    MANAGED_LABEL,
    build_image,
    container_command,
    docker_available,
    retained_container_name,
    run_container,
)
from aisbox.models import DockerContainer, Environment, Mount, RetainedSession


def test_docker_and_retained_session_records_expose_lifecycle_fields():
    container = DockerContainer(
        name="aisbox-demo1",
        status="running",
        labels={
            "dev.aisbox.managed": "true",
            "dev.aisbox.environment": "demo1",
            "dev.aisbox.agent": "claude",
        },
    )
    session = RetainedSession(
        environment="demo1",
        agent="claude",
        container="aisbox-demo1",
        status="running",
    )

    assert container.name == session.container
    assert container.labels["dev.aisbox.environment"] == session.environment
    assert session.status == "running"


def test_build_image_invokes_docker_build_with_stdin():
    runner = Mock()
    agent = get_agent("claude")

    build_image(agent, runner=runner)

    runner.assert_called_once()
    args, kwargs = runner.call_args
    assert args[0][:4] == ["docker", "build", "-t", "aisbox/claude:latest"]
    assert "--build-arg" in args[0]
    assert any(item.startswith("AISBOX_UID=") for item in args[0])
    assert any(item.startswith("AISBOX_GID=") for item in args[0])
    assert args[0][-1] == "-"
    assert kwargs["input"] == agent.dockerfile
    assert kwargs["text"] is True
    assert kwargs["check"] is True


def test_agent_dockerfile_creates_aisbox_user_with_build_time_uid_and_gid():
    dockerfile = get_agent("claude").dockerfile

    assert "ARG AISBOX_UID=1000" in dockerfile
    assert "ARG AISBOX_GID=1000" in dockerfile
    assert "usermod -l aisbox -d /home/aisbox -m" in dockerfile
    assert "groupmod -n aisbox" in dockerfile
    assert "useradd -m -u \"$AISBOX_UID\" -g \"$AISBOX_GID\"" in dockerfile
    assert "useradd -m -o" not in dockerfile


def test_docker_available_returns_false_when_command_fails():
    def failing_runner(command, **kwargs):
        raise FileNotFoundError()

    assert docker_available(runner=failing_runner) is False


def test_docker_available_returns_false_when_docker_version_fails():
    def failing_runner(command, **kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd=command)

    assert docker_available(runner=failing_runner) is False


def test_docker_available_returns_true_when_docker_version_succeeds():
    runner = Mock()

    assert docker_available(runner=runner) is True
    runner.assert_called_once_with(
        ["docker", "version", "--format", "{{.Server.Version}}"],
        check=True,
        capture_output=True,
        text=True,
    )


def test_container_command_includes_mounts_env_and_prompt():
    env = Environment(
        name="demo1",
        agent="claude",
        env={"TOKEN": "abc"},
        workspace="/tmp/workspace",
        mounts=[Mount(source="/tmp/src", alias="src")],
        image="aisbox/claude:latest",
        created_at="2026-06-05T00:00:00Z",
    )

    command = container_command(env, get_agent("claude"), "/tmp/config", "run", "hello")

    assert command[:4] == ["docker", "run", "--rm", "-w"]
    assert "-v" in command
    assert "/tmp/workspace:/workspace" in command
    assert "/tmp/config:/home/aisbox" in command
    assert "/tmp/src:/workspace/src" in command
    assert "TOKEN=abc" in command
    assert command[-2:] == ["-p", "hello"]


def test_container_command_uses_stored_environment_image():
    agent = get_agent("claude")
    env = Environment(
        name="demo1",
        agent="claude",
        env={},
        workspace="/tmp/workspace",
        mounts=[],
        image="aisbox/claude:pinned",
        created_at="2026-06-05T00:00:00Z",
    )

    command = container_command(env, agent, "/tmp/config", "run", "hello")
    image_index = command.index(agent.run_command[0]) - 1

    assert command[image_index] == "aisbox/claude:pinned"
    assert agent.image not in command


def test_container_command_start_mode_is_disposable_interactive_and_appends_attach_command():
    agent = get_agent("claude")
    env = Environment(
        name="demo1",
        agent="claude",
        env={},
        workspace="/tmp/workspace",
        mounts=[],
        image="aisbox/claude:latest",
        created_at="2026-06-05T00:00:00Z",
    )

    command = container_command(env, agent, "/tmp/config", "start")

    assert "--rm" in command
    assert "-it" in command
    assert command[-len(agent.attach_command) :] == agent.attach_command


def test_container_command_attach_alias_matches_disposable_start():
    agent = get_agent("claude")
    env = Environment(
        name="demo1",
        agent="claude",
        env={},
        workspace="/tmp/workspace",
        mounts=[],
        image="aisbox/claude:latest",
        created_at="2026-06-05T00:00:00Z",
    )

    start_command = container_command(env, agent, "/tmp/config", "start")
    attach_command = container_command(env, agent, "/tmp/config", "attach")

    assert attach_command == start_command
    assert "--rm" in attach_command


def test_container_command_retained_start_has_deterministic_name_and_labels():
    agent = get_agent("claude")
    env = Environment(
        name="demo1",
        agent="stale-environment-agent",
        env={"Z_TOKEN": "last", "A_TOKEN": "first"},
        workspace="/tmp/workspace",
        mounts=[Mount(source="/tmp/src", alias="src")],
        image="aisbox/claude:pinned",
        created_at="2026-06-05T00:00:00Z",
    )

    command = container_command(
        env,
        agent,
        "/tmp/config",
        "start",
        retained=True,
    )

    assert "--rm" not in command
    assert command[command.index("--name") + 1] == retained_container_name(env.name)
    assert command.count("--label") == 3
    assert f"{MANAGED_LABEL}=true" in command
    assert f"{ENVIRONMENT_LABEL}={env.name}" in command
    assert f"{AGENT_LABEL}={agent.name}" in command
    assert f"{AGENT_LABEL}={env.agent}" not in command
    assert "-it" in command
    assert "/tmp/workspace:/workspace" in command
    assert "/tmp/config:/home/aisbox" in command
    assert "/tmp/src:/workspace/src" in command
    assert command.index("A_TOKEN=first") < command.index("Z_TOKEN=last")
    assert "aisbox/claude:pinned" in command
    assert command[-len(agent.attach_command) :] == agent.attach_command


@pytest.mark.parametrize("mode", ["run", "shell", "attach"])
def test_container_command_rejects_retained_non_start_modes(mode):
    agent = get_agent("claude")
    env = Environment(
        name="demo1",
        agent="claude",
        env={},
        workspace="/tmp/workspace",
        mounts=[],
        image="aisbox/claude:latest",
        created_at="2026-06-05T00:00:00Z",
    )

    with pytest.raises(ValueError, match="Retained containers require start mode"):
        container_command(env, agent, "/tmp/config", mode, retained=True)


def test_container_command_shell_mode_is_interactive_and_appends_shell_command():
    agent = get_agent("claude")
    env = Environment(
        name="demo1",
        agent="claude",
        env={},
        workspace="/tmp/workspace",
        mounts=[],
        image="aisbox/claude:latest",
        created_at="2026-06-05T00:00:00Z",
    )

    command = container_command(env, agent, "/tmp/config", "shell")

    assert "--rm" in command
    assert "-it" in command
    assert command[-len(agent.shell_command) :] == agent.shell_command


def test_run_container_preserves_positional_runner_and_forwards_keyword_retained():
    runner = Mock()
    agent = get_agent("claude")
    env = Environment(
        name="demo1",
        agent="claude",
        env={},
        workspace="/tmp/workspace",
        mounts=[],
        image="aisbox/claude:latest",
        created_at="2026-06-05T00:00:00Z",
    )

    run_container(
        env,
        agent,
        "/tmp/config",
        "start",
        None,
        runner,
        retained=True,
    )

    command = runner.call_args.args[0]
    assert "--rm" not in command
    assert command[command.index("--name") + 1] == "aisbox-demo1"
    runner.assert_called_once_with(command, check=True)
