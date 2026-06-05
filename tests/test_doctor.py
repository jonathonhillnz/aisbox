from typer.testing import CliRunner

from aienv.cli import app


runner = CliRunner()


def test_doctor_success(tmp_path, monkeypatch):
    monkeypatch.setenv("AIENV_HOME", str(tmp_path / "aienv-home"))
    monkeypatch.setattr("aienv.commands.docker_available", lambda: True)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "Docker: ok" in result.stdout
    assert "State directory: ok" in result.stdout


def test_doctor_fails_when_docker_unavailable_or_not_permitted(tmp_path, monkeypatch):
    monkeypatch.setenv("AIENV_HOME", str(tmp_path / "aienv-home"))
    monkeypatch.setattr("aienv.commands.docker_available", lambda: False)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "Docker: missing, unreachable, or permission denied" in result.stdout
