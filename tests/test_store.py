import json
import os
import stat
from pathlib import Path

import pytest

from aisbox.commands import resolve_environment_name, set_default_environment
from aisbox.errors import AisboxError
from aisbox.models import Environment, Mount
from aisbox.store import EnvironmentStore


def make_env(workspace: Path) -> Environment:
    return Environment(
        name="demo1",
        agent="claude",
        env={"TOKEN": "abc"},
        workspace=str(workspace),
        mounts=[Mount(source=str(workspace / "src"), alias="src")],
        image="aisbox/claude:latest",
        created_at="2026-06-05T00:00:00Z",
    )


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_save_and_load_environment(aisbox_home, tmp_path):
    store = EnvironmentStore()
    env = make_env(tmp_path)

    store.save(env)
    loaded = store.load("demo1")

    assert loaded == env
    assert (aisbox_home / "demo1" / "environment.json").exists()


def test_managed_state_uses_restrictive_modes_regardless_of_umask(
    aisbox_home, tmp_path
):
    store = EnvironmentStore()
    previous_umask = os.umask(0o777)
    try:
        store.create_dirs("demo1", "claude")
        store.save(make_env(tmp_path))
        store.write_settings({"default_environment": "demo1"})
    finally:
        os.umask(previous_umask)

    assert mode(aisbox_home) == 0o700
    assert mode(aisbox_home / "demo1") == 0o700
    assert mode(aisbox_home / "demo1" / "config") == 0o700
    assert mode(aisbox_home / "demo1" / "files") == 0o700
    assert mode(aisbox_home / "demo1" / "environment.json") == 0o600
    assert mode(aisbox_home / "settings.json") == 0o600
    assert store.load("demo1") == make_env(tmp_path)
    assert store.read_settings() == {"default_environment": "demo1"}


@pytest.mark.parametrize("managed_file", ["environment.json", "settings.json"])
def test_managed_file_symlink_is_rejected_without_changing_external_target(
    aisbox_home, tmp_path, managed_file
):
    external_file = tmp_path / f"external-{managed_file}"
    external_file.write_text("external data\n", encoding="utf-8")
    external_file.chmod(0o640)
    store = EnvironmentStore()

    if managed_file == "environment.json":
        env_dir = aisbox_home / "demo1"
        env_dir.mkdir(parents=True)
        managed_path = env_dir / managed_file
        write = lambda: store.save(make_env(tmp_path))
    else:
        aisbox_home.mkdir()
        managed_path = aisbox_home / managed_file
        write = lambda: store.write_settings({"default_environment": "demo1"})
    managed_path.symlink_to(external_file)

    with pytest.raises(AisboxError, match="Managed state path"):
        write()

    assert external_file.read_text(encoding="utf-8") == "external data\n"
    assert mode(external_file) == 0o640


@pytest.mark.parametrize("managed_file", ["environment.json", "settings.json"])
def test_managed_fifo_is_rejected_without_changing_or_replacing_it(
    aisbox_home, tmp_path, managed_file
):
    store = EnvironmentStore()
    if managed_file == "environment.json":
        env_dir = aisbox_home / "demo1"
        env_dir.mkdir(parents=True)
        managed_path = env_dir / managed_file
        write = lambda: store.save(make_env(tmp_path))
    else:
        aisbox_home.mkdir()
        managed_path = aisbox_home / managed_file
        write = lambda: store.write_settings({"default_environment": "demo1"})
    os.mkfifo(managed_path, 0o640)
    original = managed_path.lstat()

    with pytest.raises(AisboxError, match="Managed state path"):
        write()

    current = managed_path.lstat()
    assert stat.S_ISFIFO(current.st_mode)
    assert current.st_ino == original.st_ino
    assert stat.S_IMODE(current.st_mode) == stat.S_IMODE(original.st_mode)


@pytest.mark.parametrize("managed_dir", ["environment", "config", "files"])
def test_managed_directory_symlink_is_rejected_without_changing_external_target(
    aisbox_home, tmp_path, managed_dir
):
    external_dir = tmp_path / f"external-{managed_dir}"
    external_dir.mkdir()
    external_file = external_dir / "user-data"
    external_file.write_text("external data\n", encoding="utf-8")
    external_dir.chmod(0o755)
    store = EnvironmentStore()

    aisbox_home.mkdir()
    env_dir = aisbox_home / "demo1"
    if managed_dir == "environment":
        env_dir.symlink_to(external_dir, target_is_directory=True)
    else:
        env_dir.mkdir()
        (env_dir / managed_dir).symlink_to(external_dir, target_is_directory=True)

    with pytest.raises(AisboxError, match="Managed state path"):
        store.save(make_env(tmp_path))

    assert external_file.read_text(encoding="utf-8") == "external data\n"
    assert mode(external_dir) == 0o755


def test_save_tightens_existing_managed_directories_without_creating_missing_ones(
    aisbox_home, tmp_path
):
    env_dir = aisbox_home / "demo1"
    config_dir = env_dir / "config"
    files_dir = env_dir / "files"
    config_dir.mkdir(parents=True)
    files_dir.mkdir()
    config_dir.chmod(0o755)
    files_dir.chmod(0o755)

    EnvironmentStore().save(make_env(tmp_path))

    assert mode(config_dir) == 0o700
    assert mode(files_dir) == 0o700

    env2 = make_env(tmp_path)
    env2.name = "demo2"
    EnvironmentStore().save(env2)

    assert not (aisbox_home / "demo2" / "config").exists()
    assert not (aisbox_home / "demo2" / "files").exists()


def test_unexpected_managed_file_type_is_rejected_without_changing_mode(
    aisbox_home, tmp_path
):
    environment_path = aisbox_home / "demo1" / "environment.json"
    environment_path.mkdir(parents=True)
    environment_path.chmod(0o755)

    with pytest.raises(AisboxError, match="Managed state path"):
        EnvironmentStore().save(make_env(tmp_path))

    assert environment_path.is_dir()
    assert mode(environment_path) == 0o755


def test_managed_state_tightens_existing_modes_without_changing_external_workspace(
    aisbox_home, tmp_path
):
    env_dir = aisbox_home / "demo1"
    config_dir = env_dir / "config"
    files_dir = env_dir / "files"
    external_workspace = tmp_path / "external-workspace"
    for path in [config_dir, files_dir, external_workspace]:
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o755)
    aisbox_home.chmod(0o755)
    env_dir.chmod(0o755)

    environment_path = env_dir / "environment.json"
    settings_path = aisbox_home / "settings.json"
    environment_path.write_text("{}\n", encoding="utf-8")
    settings_path.write_text("{}\n", encoding="utf-8")
    environment_path.chmod(0o644)
    settings_path.chmod(0o644)

    store = EnvironmentStore()
    store.create_dirs("demo1", "claude")
    store.save(make_env(external_workspace))
    store.write_settings({"default_environment": "demo1"})

    assert mode(aisbox_home) == 0o700
    assert mode(env_dir) == 0o700
    assert mode(config_dir) == 0o700
    assert mode(files_dir) == 0o700
    assert mode(environment_path) == 0o600
    assert mode(settings_path) == 0o600
    assert mode(external_workspace) == 0o755


def test_root_override_expands_user_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    store = EnvironmentStore(Path("~/some-aisbox-test-root"))

    assert store.root == tmp_path / "some-aisbox-test-root"


def test_create_dirs_creates_home_config_directory(aisbox_home):
    store = EnvironmentStore()

    store.create_dirs("demo1", "claude")

    assert (aisbox_home / "demo1" / "config").is_dir()
    assert not (aisbox_home / "demo1" / "config" / "claude").exists()


@pytest.mark.parametrize("agent", ["../agent", "agent/name", ".", ".."])
def test_create_dirs_rejects_path_like_agent_values_without_creating_dirs(
    aisbox_home, agent
):
    store = EnvironmentStore()

    with pytest.raises(AisboxError):
        store.create_dirs("demo1", agent)

    assert not (aisbox_home / "demo1").exists()
    assert not (aisbox_home.parent / "agent").exists()


@pytest.mark.parametrize("name", [".", ".."])
def test_env_dir_rejects_dot_segment_names(name):
    store = EnvironmentStore()

    with pytest.raises(AisboxError):
        store.env_dir(name)


@pytest.mark.parametrize("name", [".", ".."])
def test_save_rejects_dot_segment_names(aisbox_home, tmp_path, name):
    store = EnvironmentStore()
    env = make_env(tmp_path)
    env.name = name

    with pytest.raises(AisboxError):
        store.save(env)

    assert not (aisbox_home / "environment.json").exists()
    assert not (aisbox_home.parent / "environment.json").exists()


@pytest.mark.parametrize("name", [".", ".."])
def test_delete_rejects_dot_segment_names_without_removing_paths(
    aisbox_home, monkeypatch, name
):
    store = EnvironmentStore()
    aisbox_home.mkdir(parents=True)
    removed_paths = []

    def fake_rmtree(path):
        removed_paths.append(path)

    monkeypatch.setattr("aisbox.store.shutil.rmtree", fake_rmtree)

    with pytest.raises(AisboxError):
        store.delete(name)

    assert removed_paths == []


def test_load_missing_environment_raises(aisbox_home):
    store = EnvironmentStore()

    with pytest.raises(AisboxError):
        store.load("missing")


@pytest.mark.parametrize("alias", ["../src", "/src", "src/repo", "src..repo"])
def test_load_rejects_persisted_unsafe_mount_aliases(aisbox_home, tmp_path, alias):
    store = EnvironmentStore()
    env_dir = aisbox_home / "demo1"
    env_dir.mkdir(parents=True)
    payload = {
        "name": "demo1",
        "agent": "claude",
        "env": {},
        "workspace": str(tmp_path),
        "mounts": [{"source": str(tmp_path), "alias": alias}],
        "image": "aisbox/claude:latest",
        "created_at": "2026-06-05T00:00:00Z",
    }
    (env_dir / "environment.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(AisboxError):
        store.load("demo1")


@pytest.mark.parametrize(
    ("field", "value"),
    [("name", ".."), ("agent", "../claude")],
)
def test_load_rejects_persisted_unsafe_environment_fields(
    aisbox_home, tmp_path, field, value
):
    store = EnvironmentStore()
    env_dir = aisbox_home / "demo1"
    env_dir.mkdir(parents=True)
    payload = {
        "name": "demo1",
        "agent": "claude",
        "env": {},
        "workspace": str(tmp_path),
        "mounts": [],
        "image": "aisbox/claude:latest",
        "created_at": "2026-06-05T00:00:00Z",
    }
    payload[field] = value
    (env_dir / "environment.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(AisboxError):
        store.load("demo1")


def test_list_environments_sorts_by_name(aisbox_home, tmp_path):
    store = EnvironmentStore()
    store.save(make_env(tmp_path))
    env2 = make_env(tmp_path)
    env2.name = "alpha"
    store.save(env2)

    assert [env.name for env in store.list()] == ["alpha", "demo1"]


def test_delete_environment_removes_directory(aisbox_home, tmp_path):
    store = EnvironmentStore()
    store.save(make_env(tmp_path))

    store.delete("demo1")

    assert not (aisbox_home / "demo1").exists()


def test_delete_partial_directory_without_state_file_raises(aisbox_home):
    store = EnvironmentStore()
    partial_dir = aisbox_home / "partial"
    partial_dir.mkdir(parents=True)

    with pytest.raises(AisboxError):
        store.delete("partial")

    assert partial_dir.exists()


def test_set_and_load_default_environment(aisbox_home, tmp_path):
    store = EnvironmentStore()
    store.save(make_env(tmp_path))

    store.set_default_environment("demo1")

    assert store.load_default_environment() == "demo1"
    payload = json.loads((aisbox_home / "settings.json").read_text(encoding="utf-8"))
    assert payload == {"default_environment": "demo1"}


def test_set_default_environment_rejects_missing_environment(aisbox_home):
    store = EnvironmentStore()

    with pytest.raises(AisboxError, match="Environment does not exist: missing"):
        store.set_default_environment("missing")

    assert not (aisbox_home / "settings.json").exists()


def test_delete_default_environment_clears_only_default_setting(aisbox_home, tmp_path):
    store = EnvironmentStore()
    store.save(make_env(tmp_path))
    store.write_settings({"default_environment": "demo1", "future_setting": "kept"})

    store.delete("demo1")

    assert store.read_settings() == {"future_setting": "kept"}


def test_load_default_environment_rejects_unsafe_persisted_name(aisbox_home):
    store = EnvironmentStore()
    aisbox_home.mkdir(parents=True)
    (aisbox_home / "settings.json").write_text(
        json.dumps({"default_environment": "../demo"}),
        encoding="utf-8",
    )

    with pytest.raises(AisboxError, match=r"Environment name must match"):
        store.load_default_environment()


def test_command_resolve_environment_name_prefers_explicit_name(aisbox_home, tmp_path):
    store = EnvironmentStore()
    store.save(make_env(tmp_path))
    env2 = make_env(tmp_path)
    env2.name = "demo2"
    store.save(env2)
    store.set_default_environment("demo1")

    assert resolve_environment_name("demo2", store) == "demo2"


def test_command_resolve_environment_name_uses_default(aisbox_home, tmp_path):
    store = EnvironmentStore()
    store.save(make_env(tmp_path))
    store.set_default_environment("demo1")

    assert resolve_environment_name(None, store) == "demo1"


def test_command_resolve_environment_name_requires_name_or_default(aisbox_home):
    store = EnvironmentStore()

    with pytest.raises(
        AisboxError,
        match="No environment specified and no default environment is set",
    ):
        resolve_environment_name(None, store)


def test_command_set_default_environment_returns_name(aisbox_home, tmp_path):
    store = EnvironmentStore()
    store.save(make_env(tmp_path))

    assert set_default_environment("demo1", store) == "demo1"
    assert store.load_default_environment() == "demo1"
