import os
import stat
import tempfile

import pytest
from typer.testing import CliRunner

from aisbox.cli import app


runner = CliRunner()


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_doctor_success_creates_private_state_root_regardless_of_umask(
    tmp_path, monkeypatch
):
    home = tmp_path / "aisbox-home"
    monkeypatch.setenv("AISBOX_HOME", str(home))
    monkeypatch.setattr("aisbox.commands.docker_available", lambda: True)

    previous_umask = os.umask(0o022)
    try:
        result = runner.invoke(app, ["doctor"])
    finally:
        os.umask(previous_umask)

    assert result.exit_code == 0
    assert "Docker: ok" in result.stdout
    assert "State directory: ok" in result.stdout
    assert "Supported agents: claude, codex" in result.stdout
    assert mode(home) == 0o700


def test_doctor_tightens_existing_state_root(tmp_path, monkeypatch):
    home = tmp_path / "aisbox-home"
    home.mkdir()
    home.chmod(0o755)
    monkeypatch.setenv("AISBOX_HOME", str(home))
    monkeypatch.setattr("aisbox.commands.docker_available", lambda: True)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "State directory: ok" in result.stdout
    assert mode(home) == 0o700


def test_doctor_preserves_existing_write_test_file_and_cleans_probe(tmp_path, monkeypatch):
    home = tmp_path / "aisbox-home"
    home.mkdir()
    existing_probe_name = home / ".doctor-write-test"
    existing_probe_name.write_text("user data\n", encoding="utf-8")
    monkeypatch.setenv("AISBOX_HOME", str(home))
    monkeypatch.setattr("aisbox.commands.docker_available", lambda: True)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert existing_probe_name.read_text(encoding="utf-8") == "user data\n"
    assert sorted(path.name for path in home.glob(".doctor-*")) == [".doctor-write-test"]


def test_doctor_fails_when_docker_unavailable_or_not_permitted(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    monkeypatch.setattr("aisbox.commands.docker_available", lambda: False)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "Docker: missing, unreachable, or permission denied" in result.stdout


def test_doctor_reports_state_directory_os_error(tmp_path, monkeypatch):
    home = tmp_path / "aisbox-home"
    monkeypatch.setenv("AISBOX_HOME", str(home))
    monkeypatch.setattr("aisbox.commands.docker_available", lambda: True)

    def fail_probe(*args, **kwargs):
        raise OSError("no writes here")

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", fail_probe)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert f"State directory: not writable: {home} (no writes here)" in result.stdout


@pytest.mark.parametrize("root_type", ["symlink", "file"])
def test_doctor_reports_invalid_state_root_without_traceback(
    tmp_path, monkeypatch, root_type
):
    home = tmp_path / "aisbox-home"
    if root_type == "symlink":
        external_dir = tmp_path / "external-state"
        external_dir.mkdir()
        external_dir.chmod(0o755)
        home.symlink_to(external_dir, target_is_directory=True)
    else:
        home.write_text("not a directory\n", encoding="utf-8")
    monkeypatch.setenv("AISBOX_HOME", str(home))
    monkeypatch.setattr("aisbox.commands.docker_available", lambda: True)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "State directory: not writable:" in result.stdout
    assert "State directory: ok" not in result.stdout
    assert "Traceback" not in result.stderr
    if root_type == "symlink":
        assert mode(external_dir) == 0o755
