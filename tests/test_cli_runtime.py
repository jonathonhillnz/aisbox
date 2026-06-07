import subprocess
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from aisbox.cli import app
from aisbox.commands import (
    attach_environment,
    delete_environment,
    kill_session,
    list_sessions,
    start_environment,
)
from aisbox.errors import AisboxError
from aisbox.models import DockerContainer


runner = CliRunner()


def setup_env(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    monkeypatch.setattr("aisbox.commands.build_image", lambda agent: None)
    result = runner.invoke(app, ["create", "-n", "demo1", "-a", "claude", "-e", "TOKEN=abc"])
    assert result.exit_code == 0


def managed_container(
    *,
    environment: str = "demo1",
    agent: str = "claude",
    status: str = "running",
    name: str | None = None,
    labels: dict[str, str] | None = None,
) -> DockerContainer:
    return DockerContainer(
        name=name or f"aisbox-{environment}",
        status=status,
        labels=labels
        or {
            "dev.aisbox.managed": "true",
            "dev.aisbox.environment": environment,
            "dev.aisbox.agent": agent,
        },
    )


def test_start_environment_without_keep_runs_disposable_start(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    run_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", run_mock)

    start_environment("demo1", keep=False)

    assert run_mock.call_args.args[3] == "start"
    assert run_mock.call_args.kwargs == {}


def test_retained_start_creates_missing_session(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr("aisbox.commands.inspect_container", lambda name: None)
    run_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", run_mock)

    start_environment("demo1", keep=True)

    assert run_mock.call_args.args[3] == "start"
    assert run_mock.call_args.kwargs == {"retained": True}


def test_attach_joins_running_retained_session(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "aisbox.commands.inspect_container",
        lambda name: managed_container(),
    )
    attach_mock = Mock()
    monkeypatch.setattr("aisbox.commands.attach_container", attach_mock)

    attach_environment("demo1")

    attach_mock.assert_called_once_with("aisbox-demo1")


def test_attach_replaces_stopped_retained_session(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "aisbox.commands.inspect_container",
        lambda name: managed_container(status="exited"),
    )
    remove_mock = Mock()
    run_mock = Mock()
    monkeypatch.setattr("aisbox.commands.remove_container", remove_mock)
    monkeypatch.setattr("aisbox.commands.run_container", run_mock)

    attach_environment("demo1")

    remove_mock.assert_called_once_with("aisbox-demo1")
    assert run_mock.call_args.args[3] == "start"
    assert run_mock.call_args.kwargs == {"retained": True}


@pytest.mark.parametrize(
    "container",
    [
        DockerContainer(name="aisbox-demo1", status="running", labels={}),
        managed_container(name="not-aisbox-demo1"),
        managed_container(
            labels={
                "dev.aisbox.managed": "true",
                "dev.aisbox.environment": "other",
                "dev.aisbox.agent": "claude",
            }
        ),
        managed_container(
            labels={
                "dev.aisbox.managed": "true",
                "dev.aisbox.environment": "demo1",
                "dev.aisbox.agent": "codex",
            }
        ),
    ],
)
def test_attach_rejects_unowned_name_collision(
    tmp_path, monkeypatch, container
):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "aisbox.commands.inspect_container",
        lambda name: container,
    )
    attach_mock = Mock()
    remove_mock = Mock()
    monkeypatch.setattr("aisbox.commands.attach_container", attach_mock)
    monkeypatch.setattr("aisbox.commands.remove_container", remove_mock)

    with pytest.raises(AisboxError, match="not managed by aisbox"):
        attach_environment("demo1")

    attach_mock.assert_not_called()
    remove_mock.assert_not_called()


def test_list_sessions_returns_only_valid_running_sessions(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    create = runner.invoke(app, ["create", "-n", "demo2", "-a", "codex"])
    assert create.exit_code == 0
    monkeypatch.setattr(
        "aisbox.commands.list_retained_containers",
        lambda: [
            managed_container(environment="demo2", agent="codex"),
            managed_container(),
            managed_container(environment="demo1", status="exited"),
            managed_container(environment="missing"),
            managed_container(environment="demo2", agent="claude"),
            managed_container(environment="demo2", agent="codex", name="other"),
            managed_container(labels={"dev.aisbox.managed": "true"}),
            managed_container(
                labels={
                    "dev.aisbox.managed": "false",
                    "dev.aisbox.environment": "demo1",
                    "dev.aisbox.agent": "claude",
                }
            ),
        ],
    )

    sessions = list_sessions()

    assert [
        (item.environment, item.agent, item.container, item.status)
        for item in sessions
    ] == [
        ("demo1", "claude", "aisbox-demo1", "running"),
        ("demo2", "codex", "aisbox-demo2", "running"),
    ]


@pytest.mark.parametrize("status", ["running", "exited"])
def test_kill_removes_owned_running_or_stopped_container(
    tmp_path, monkeypatch, status
):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "aisbox.commands.inspect_container",
        lambda name: managed_container(status=status),
    )
    remove_mock = Mock()
    monkeypatch.setattr("aisbox.commands.remove_container", remove_mock)

    kill_session("demo1")

    remove_mock.assert_called_once_with("aisbox-demo1")


def test_kill_errors_when_retained_container_is_missing(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr("aisbox.commands.inspect_container", lambda name: None)

    with pytest.raises(AisboxError, match="No retained session"):
        kill_session("demo1")


def test_attach_translates_docker_inspection_failure(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "aisbox.commands.inspect_container",
        lambda name: (_ for _ in ()).throw(
            subprocess.CalledProcessError(
                returncode=1,
                cmd=["docker", "container", "inspect", name],
            )
        ),
    )

    with pytest.raises(
        AisboxError,
        match="Docker retained session operation failed for environment: demo1",
    ):
        attach_environment("demo1")


@pytest.mark.parametrize("status", ["running", "exited"])
def test_delete_refuses_when_owned_retained_container_exists(
    tmp_path, monkeypatch, status
):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "aisbox.commands.inspect_container",
        lambda name: managed_container(status=status),
    )

    with pytest.raises(AisboxError, match=r"aisbox kill -n demo1"):
        delete_environment("demo1")


def test_run_builds_non_interactive_docker_command(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    runner_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", runner_mock)

    result = runner.invoke(app, ["run", "-n", "demo1", "--", "hello"])

    assert result.exit_code == 0
    env, agent, config_source, mode, prompt = runner_mock.call_args.args
    assert env.name == "demo1"
    assert agent.name == "claude"
    assert config_source.endswith("/config")
    assert mode == "run"
    assert prompt == "hello"


def test_run_without_prompt_passes_none(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    runner_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", runner_mock)

    result = runner.invoke(app, ["run", "-n", "demo1"])

    assert result.exit_code == 0
    assert runner_mock.call_args.args[4] is None


def test_run_uses_default_environment_when_name_omitted(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    runner.invoke(app, ["set", "default", "-n", "demo1"])
    runner_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", runner_mock)

    result = runner.invoke(app, ["run", "--", "hello"])

    assert result.exit_code == 0
    env, agent, config_source, mode, prompt = runner_mock.call_args.args
    assert env.name == "demo1"
    assert agent.name == "claude"
    assert config_source.endswith("/config")
    assert mode == "run"
    assert prompt == "hello"


def test_run_explicit_name_overrides_default_environment(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr("aisbox.commands.build_image", lambda agent: None)
    runner.invoke(app, ["create", "-n", "demo2", "-a", "claude"])
    runner.invoke(app, ["set", "default", "-n", "demo1"])
    runner_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", runner_mock)

    result = runner.invoke(app, ["run", "-n", "demo2", "--", "hello"])

    assert result.exit_code == 0
    env = runner_mock.call_args.args[0]
    assert env.name == "demo2"


def test_attach_and_shell_use_interactive_modes(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    runner_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", runner_mock)

    attach = runner.invoke(app, ["attach", "-n", "demo1"])
    shell = runner.invoke(app, ["shell", "-n", "demo1"])

    assert attach.exit_code == 0
    assert shell.exit_code == 0
    assert runner_mock.call_args_list[0].args[3] == "attach"
    assert runner_mock.call_args_list[1].args[3] == "shell"


def test_rebuild_invokes_image_build_for_stored_agent(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    build_mock = Mock()
    monkeypatch.setattr("aisbox.commands.build_image", build_mock)

    result = runner.invoke(app, ["rebuild", "-n", "demo1"])

    assert result.exit_code == 0
    assert "Rebuilt demo1" in result.stdout
    assert build_mock.call_args.args[0].name == "claude"
