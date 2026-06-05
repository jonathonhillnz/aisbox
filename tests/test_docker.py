from pathlib import Path
from unittest.mock import Mock

from aienv.agents import get_agent
from aienv.docker import build_image, docker_available
from aienv.models import Environment


def test_build_image_invokes_docker_build_with_stdin(tmp_path):
    runner = Mock()
    agent = get_agent("claude")

    build_image(agent, runner=runner)

    runner.assert_called_once()
    args, kwargs = runner.call_args
    assert args[0] == ["docker", "build", "-t", "aienv/claude:latest", "-"]
    assert kwargs["input"] == agent.dockerfile
    assert kwargs["text"] is True
    assert kwargs["check"] is True


def test_docker_available_returns_false_when_command_fails():
    def failing_runner(command, **kwargs):
        raise FileNotFoundError()

    assert docker_available(runner=failing_runner) is False
