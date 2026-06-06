from pathlib import Path

import pytest
from typer.testing import CliRunner

from aisbox.cli import app
from aisbox.commands import set_env_vars, unset_env_vars
from aisbox.errors import AisboxError
from aisbox.models import Environment
from aisbox.store import EnvironmentStore


runner = CliRunner()


def make_stored_environment(tmp_path: Path) -> EnvironmentStore:
    store = EnvironmentStore(tmp_path / "aisbox-home")
    store.save(
        Environment(
            name="demo1",
            agent="claude",
            env={"EXISTING": "old", "REMOVE": "one", "ALSO_REMOVE": "two"},
            workspace=str(tmp_path),
            mounts=[],
            image="aisbox/claude:latest",
            created_at="2026-06-07T00:00:00Z",
        )
    )
    return store


def create_demo(monkeypatch):
    monkeypatch.setattr("aisbox.commands.build_image", lambda agent: None)
    result = runner.invoke(app, ["create", "-n", "demo1", "-a", "claude"])
    assert result.exit_code == 0


def test_mount_and_unmount(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
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
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
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
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
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
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    source = tmp_path / "source"
    source.mkdir()
    create_demo(monkeypatch)

    for alias in ["../src", "/src", "src/repo"]:
        result = runner.invoke(app, ["mount", "-n", "demo1", str(source), alias])

        assert result.exit_code == 1
        assert "Error:" in result.stderr
        assert "Mount alias must be a relative name under /workspace" in result.stderr


def test_unmount_missing_alias_exits_nonzero_with_error(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    create_demo(monkeypatch)

    result = runner.invoke(app, ["unmount", "-n", "demo1", "src"])

    assert result.exit_code == 1
    assert "Error:" in result.stderr
    assert "Mount alias does not exist: src" in result.stderr


def test_env_set_and_unset(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    create_demo(monkeypatch)

    set_result = runner.invoke(
        app,
        [
            "env",
            "set",
            "-n",
            "demo1",
            "-e",
            "TOKEN=",
            "-e",
            "MODE=explicit",
        ],
        input="prompted\n",
    )
    inspected = runner.invoke(app, ["inspect", "-n", "demo1"])
    unset_result = runner.invoke(
        app,
        ["env", "unset", "-n", "demo1", "-e", "TOKEN", "-e", "MODE"],
    )
    inspected_again = runner.invoke(app, ["inspect", "-n", "demo1"])

    assert set_result.exit_code == 0
    assert "Set TOKEN" in set_result.stdout
    assert "Set MODE" in set_result.stdout
    assert "prompted" not in set_result.stdout
    assert "explicit" not in set_result.stdout
    assert "TOKEN=<set>" in inspected.stdout
    assert "MODE=<set>" in inspected.stdout
    assert unset_result.exit_code == 0
    assert "Unset TOKEN" in unset_result.stdout
    assert "Unset MODE" in unset_result.stdout
    assert "TOKEN=<set>" not in inspected_again.stdout
    assert "MODE=<set>" not in inspected_again.stdout


def test_env_set_overwrites_existing_key_and_redacts_new_value(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    create_demo(monkeypatch)

    first = runner.invoke(app, ["env", "set", "-n", "demo1", "-e", "TOKEN=abc"])
    second = runner.invoke(app, ["env", "set", "-n", "demo1", "-e", "TOKEN=xyz"])
    inspected = runner.invoke(app, ["inspect", "-n", "demo1"])

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert "Set TOKEN" in second.stdout
    assert "TOKEN=<set>" in inspected.stdout
    assert "abc" not in inspected.stdout
    assert "xyz" not in inspected.stdout


def test_env_unset_missing_key_exits_nonzero_with_error(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    create_demo(monkeypatch)

    result = runner.invoke(app, ["env", "unset", "-n", "demo1", "-e", "TOKEN"])

    assert result.exit_code == 1
    assert "Error:" in result.stderr
    assert "Environment variable is not set: TOKEN" in result.stderr


@pytest.mark.parametrize(
    "args",
    [
        ["env", "set", "-n", "demo1", "TOKEN=abc"],
        ["env", "unset", "-n", "demo1", "TOKEN"],
    ],
)
def test_env_commands_reject_old_positional_syntax(tmp_path, monkeypatch, args):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    create_demo(monkeypatch)

    result = runner.invoke(app, args)

    assert result.exit_code != 0


def test_set_env_vars_sets_multiple_values_with_last_duplicate_winning(tmp_path):
    store = make_stored_environment(tmp_path)

    keys = set_env_vars(
        "demo1",
        ["TOKEN=abc", "EXISTING=new", "TOKEN=final"],
        store=store,
    )

    assert keys == ["TOKEN", "EXISTING", "TOKEN"]
    assert store.load("demo1").env == {
        "EXISTING": "new",
        "REMOVE": "one",
        "ALSO_REMOVE": "two",
        "TOKEN": "final",
    }


def test_set_env_vars_invalid_assignment_is_atomic(tmp_path):
    store = make_stored_environment(tmp_path)
    original = store.load("demo1").env

    with pytest.raises(AisboxError, match="Environment variable must be KEY=VALUE"):
        set_env_vars("demo1", ["TOKEN=abc", "INVALID"], store=store)

    assert store.load("demo1").env == original


def test_unset_env_vars_removes_multiple_values(tmp_path):
    store = make_stored_environment(tmp_path)

    keys = unset_env_vars("demo1", ["REMOVE", "ALSO_REMOVE"], store=store)

    assert keys == ["REMOVE", "ALSO_REMOVE"]
    assert store.load("demo1").env == {"EXISTING": "old"}


@pytest.mark.parametrize(
    ("keys", "message"),
    [
        (["REMOVE", "MISSING"], "Environment variable is not set: MISSING"),
        (["REMOVE", "REMOVE"], "Environment variable keys must not be repeated"),
        (["REMOVE", "BAD-KEY"], "Environment variable key must match"),
    ],
)
def test_unset_env_vars_validation_is_atomic(tmp_path, keys, message):
    store = make_stored_environment(tmp_path)
    original = store.load("demo1").env

    with pytest.raises(AisboxError, match=message):
        unset_env_vars("demo1", keys, store=store)

    assert store.load("demo1").env == original
