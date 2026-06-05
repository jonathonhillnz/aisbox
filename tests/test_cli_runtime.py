from unittest.mock import Mock

from typer.testing import CliRunner

from aisbox.cli import app


runner = CliRunner()


def setup_env(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    monkeypatch.setattr("aisbox.commands.build_image", lambda agent: None)
    result = runner.invoke(app, ["create", "-n", "demo1", "-a", "claude", "-e", "TOKEN=abc"])
    assert result.exit_code == 0


def test_run_builds_non_interactive_docker_command(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    runner_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", runner_mock)

    result = runner.invoke(app, ["run", "-n", "demo1", "--", "hello"])

    assert result.exit_code == 0
    env, agent, config_source, mode, prompt = runner_mock.call_args.args
    assert env.name == "demo1"
    assert agent.name == "claude"
    assert config_source.endswith("/config/claude")
    assert mode == "run"
    assert prompt == "hello"


def test_run_without_prompt_passes_none(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    runner_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", runner_mock)

    result = runner.invoke(app, ["run", "-n", "demo1"])

    assert result.exit_code == 0
    assert runner_mock.call_args.args[4] is None


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
