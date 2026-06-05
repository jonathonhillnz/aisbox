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
