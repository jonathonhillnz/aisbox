from typer.testing import CliRunner

from aienv.cli import app


runner = CliRunner()


def create_demo(monkeypatch):
    monkeypatch.setattr("aienv.commands.build_image", lambda agent: None)
    result = runner.invoke(app, ["create", "-n", "demo1", "-a", "claude"])
    assert result.exit_code == 0


def test_mount_and_unmount(tmp_path, monkeypatch):
    monkeypatch.setenv("AIENV_HOME", str(tmp_path / "aienv-home"))
    source = tmp_path / "source"
    source.mkdir()
    create_demo(monkeypatch)

    mounted = runner.invoke(app, ["mount", "-n", "demo1", str(source), "src"])
    inspected = runner.invoke(app, ["inspect", "-n", "demo1"])
    unmounted = runner.invoke(app, ["unmount", "-n", "demo1", "src"])
    inspected_again = runner.invoke(app, ["inspect", "-n", "demo1"])

    assert mounted.exit_code == 0
    assert "Mounted src" in mounted.stdout
    assert str(source.resolve()) in inspected.stdout
    assert unmounted.exit_code == 0
    assert "Unmounted src" in unmounted.stdout
    assert "src:" not in inspected_again.stdout


def test_env_set_and_unset(tmp_path, monkeypatch):
    monkeypatch.setenv("AIENV_HOME", str(tmp_path / "aienv-home"))
    create_demo(monkeypatch)

    set_result = runner.invoke(app, ["env", "set", "-n", "demo1", "TOKEN=abc"])
    inspected = runner.invoke(app, ["inspect", "-n", "demo1"])
    unset_result = runner.invoke(app, ["env", "unset", "-n", "demo1", "TOKEN"])
    inspected_again = runner.invoke(app, ["inspect", "-n", "demo1"])

    assert set_result.exit_code == 0
    assert "Set TOKEN" in set_result.stdout
    assert "TOKEN=<set>" in inspected.stdout
    assert "abc" not in inspected.stdout
    assert unset_result.exit_code == 0
    assert "Unset TOKEN" in unset_result.stdout
    assert "TOKEN=<set>" not in inspected_again.stdout
