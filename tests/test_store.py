import json
from pathlib import Path

import pytest

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


def test_save_and_load_environment(aisbox_home, tmp_path):
    store = EnvironmentStore()
    env = make_env(tmp_path)

    store.save(env)
    loaded = store.load("demo1")

    assert loaded == env
    assert (aisbox_home / "demo1" / "environment.json").exists()


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
