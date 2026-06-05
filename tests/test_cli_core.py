from typer.testing import CliRunner

from aienv.cli import app


runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "aienv" in result.stdout


def test_list_empty_environment_home(tmp_path, monkeypatch):
    monkeypatch.setenv("AIENV_HOME", str(tmp_path / "aienv-home"))

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "No environments found" in result.stdout


def test_create_list_and_inspect_environment(tmp_path, monkeypatch):
    home = tmp_path / "aienv-home"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("AIENV_HOME", str(home))
    monkeypatch.setattr("aienv.commands.build_image", lambda agent: None)

    create = runner.invoke(
        app,
        [
            "create",
            "-n",
            "demo1",
            "-a",
            "claude",
            "-e",
            "TOKEN=abc",
            "--workspace",
            str(workspace),
        ],
    )
    listed = runner.invoke(app, ["list"])
    inspected = runner.invoke(app, ["inspect", "-n", "demo1"])

    assert create.exit_code == 0
    assert "Created demo1" in create.stdout
    assert listed.exit_code == 0
    assert "demo1" in listed.stdout
    assert "claude" in listed.stdout
    assert inspected.exit_code == 0
    assert "workspace" in inspected.stdout
    assert "TOKEN" in inspected.stdout
    assert "abc" not in inspected.stdout


def test_delete_environment_with_force(tmp_path, monkeypatch):
    monkeypatch.setenv("AIENV_HOME", str(tmp_path / "aienv-home"))
    monkeypatch.setattr("aienv.commands.build_image", lambda agent: None)
    runner.invoke(app, ["create", "-n", "demo1", "-a", "claude"])

    result = runner.invoke(app, ["delete", "-n", "demo1", "--force"])

    assert result.exit_code == 0
    assert "Deleted demo1" in result.stdout
    assert runner.invoke(app, ["list"]).stdout.strip() == "No environments found"
