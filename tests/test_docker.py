import subprocess
from unittest.mock import Mock

from aisbox.agents import get_agent
from aisbox.docker import build_image, container_command, docker_available
from aisbox.models import Environment, Mount


def test_build_image_invokes_docker_build_with_stdin():
    runner = Mock()
    agent = get_agent("claude")

    build_image(agent, runner=runner)

    runner.assert_called_once()
    args, kwargs = runner.call_args
    assert args[0] == ["docker", "build", "-t", "aisbox/claude:latest", "-"]
    assert kwargs["input"] == agent.dockerfile
    assert kwargs["text"] is True
    assert kwargs["check"] is True


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

    command = container_command(env, get_agent("claude"), "/tmp/config/claude", "run", "hello")

    assert command[:4] == ["docker", "run", "--rm", "-w"]
    assert "-v" in command
    assert "/tmp/workspace:/workspace" in command
    assert "/tmp/config/claude:/home/aisbox/.claude" in command
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

    command = container_command(env, agent, "/tmp/config/claude", "run", "hello")
    image_index = command.index(agent.run_command[0]) - 1

    assert command[image_index] == "aisbox/claude:pinned"
    assert agent.image not in command


def test_container_command_attach_mode_is_interactive_and_appends_attach_command():
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

    command = container_command(env, agent, "/tmp/config/claude", "attach")

    assert "-it" in command
    assert command[-len(agent.attach_command) :] == agent.attach_command


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

    command = container_command(env, agent, "/tmp/config/claude", "shell")

    assert "-it" in command
    assert command[-len(agent.shell_command) :] == agent.shell_command
