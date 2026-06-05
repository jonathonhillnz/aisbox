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


def test_mount_rejects_file_path_and_missing_source(tmp_path, monkeypatch):
    monkeypatch.setenv("AIENV_HOME", str(tmp_path / "aienv-home"))
    source_file = tmp_path / "source.txt"
    source_file.write_text("not a directory")
    missing_source = tmp_path / "missing"
    create_demo(monkeypatch)

    file_result = runner.invoke(app, ["mount", "-n", "demo1", str(source_file), "src"])
    missing_result = runner.invoke(app, ["mount", "-n", "demo1", str(missing_source), "src"])

    assert file_result.exit_code == 1
    assert "Error:" in file_result.stderr
    assert "Mount source path must be an existing directory" in file_result.stderr
    assert str(source_file.resolve()) in file_result.stderr
    assert missing_result.exit_code == 1
    assert "Error:" in missing_result.stderr
    assert "Mount source path must be an existing directory" in missing_result.stderr
    assert str(missing_source.resolve()) in missing_result.stderr


def test_mount_rejects_duplicate_alias(tmp_path, monkeypatch):
    monkeypatch.setenv("AIENV_HOME", str(tmp_path / "aienv-home"))
    source = tmp_path / "source"
    source.mkdir()
    create_demo(monkeypatch)

    mounted = runner.invoke(app, ["mount", "-n", "demo1", str(source), "src"])
    duplicate = runner.invoke(app, ["mount", "-n", "demo1", str(source), "src"])

    assert mounted.exit_code == 0
    assert duplicate.exit_code == 1
    assert "Error:" in duplicate.stderr
    assert "Mount alias already exists: src" in duplicate.stderr


def test_mount_rejects_path_like_aliases_through_cli(tmp_path, monkeypatch):
    monkeypatch.setenv("AIENV_HOME", str(tmp_path / "aienv-home"))
    source = tmp_path / "source"
    source.mkdir()
    create_demo(monkeypatch)

    for alias in ["../src", "/src", "src/repo"]:
        result = runner.invoke(app, ["mount", "-n", "demo1", str(source), alias])

        assert result.exit_code == 1
        assert "Error:" in result.stderr
        assert "Mount alias must be a relative name under /workspace" in result.stderr


def test_unmount_missing_alias_exits_nonzero_with_error(tmp_path, monkeypatch):
    monkeypatch.setenv("AIENV_HOME", str(tmp_path / "aienv-home"))
    create_demo(monkeypatch)

    result = runner.invoke(app, ["unmount", "-n", "demo1", "src"])

    assert result.exit_code == 1
    assert "Error:" in result.stderr
    assert "Mount alias does not exist: src" in result.stderr


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


def test_env_set_overwrites_existing_key_and_redacts_new_value(tmp_path, monkeypatch):
    monkeypatch.setenv("AIENV_HOME", str(tmp_path / "aienv-home"))
    create_demo(monkeypatch)

    first = runner.invoke(app, ["env", "set", "-n", "demo1", "TOKEN=abc"])
    second = runner.invoke(app, ["env", "set", "-n", "demo1", "TOKEN=xyz"])
    inspected = runner.invoke(app, ["inspect", "-n", "demo1"])

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert "Set TOKEN" in second.stdout
    assert "TOKEN=<set>" in inspected.stdout
    assert "abc" not in inspected.stdout
    assert "xyz" not in inspected.stdout


def test_env_unset_missing_key_exits_nonzero_with_error(tmp_path, monkeypatch):
    monkeypatch.setenv("AIENV_HOME", str(tmp_path / "aienv-home"))
    create_demo(monkeypatch)

    result = runner.invoke(app, ["env", "unset", "-n", "demo1", "TOKEN"])

    assert result.exit_code == 1
    assert "Error:" in result.stderr
    assert "Environment variable is not set: TOKEN" in result.stderr
