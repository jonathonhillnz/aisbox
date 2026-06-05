from pathlib import Path
import subprocess

from typer.testing import CliRunner

from aisbox.cli import app
from aisbox.errors import AisboxError


runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "aisbox" in result.stdout


def test_list_empty_environment_home(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "No environments found" in result.stdout


def test_create_list_and_inspect_environment(tmp_path, monkeypatch):
    home = tmp_path / "aisbox-home"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("AISBOX_HOME", str(home))
    monkeypatch.setattr("aisbox.commands.build_image", lambda agent: None)

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


def test_create_reports_docker_not_found_without_traceback(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    monkeypatch.setattr(
        "aisbox.commands.build_image",
        lambda agent: (_ for _ in ()).throw(FileNotFoundError("docker")),
    )

    result = runner.invoke(app, ["create", "-n", "demo1", "-a", "claude"])

    assert result.exit_code == 1
    assert "Error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_create_reports_docker_build_failure_without_traceback(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    monkeypatch.setattr(
        "aisbox.commands.build_image",
        lambda agent: (_ for _ in ()).throw(
            subprocess.CalledProcessError(returncode=1, cmd=["docker", "build"])
        ),
    )

    result = runner.invoke(app, ["create", "-n", "demo1", "-a", "claude"])

    assert result.exit_code == 1
    assert "Error:" in result.stderr
    assert "Docker image build failed" in result.stderr
    assert "Traceback" not in result.stderr


def test_list_reports_store_errors(monkeypatch):
    monkeypatch.setattr(
        "aisbox.cli.list_environments",
        lambda: (_ for _ in ()).throw(AisboxError("boom")),
    )

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 1
    assert "Error: boom" in result.stderr


def test_delete_environment_with_force(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    monkeypatch.setattr("aisbox.commands.build_image", lambda agent: None)
    runner.invoke(app, ["create", "-n", "demo1", "-a", "claude"])

    result = runner.invoke(app, ["delete", "-n", "demo1", "--force"])

    assert result.exit_code == 0
    assert "Deleted demo1" in result.stdout
    assert runner.invoke(app, ["list"]).stdout.strip() == "No environments found"


def test_readme_documents_primary_commands():
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(
        encoding="utf-8"
    )

    for command in [
        "aisbox create",
        "aisbox run",
        "aisbox attach",
        "aisbox shell",
        "aisbox list",
        "aisbox inspect",
        "aisbox rebuild",
        "aisbox mount",
        "aisbox unmount",
        "aisbox env set",
        "aisbox env unset",
        "aisbox doctor",
        "aisbox delete",
    ]:
        assert command in readme

    assert (
        "Host `~/.claude` and `~/.codex` directories are not copied or mounted."
        in readme
    )
    assert "does not run Docker through `sudo`" in readme
    assert "AISBOX_HOME" in readme
