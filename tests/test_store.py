from pathlib import Path

import pytest

from aienv.errors import AienvError
from aienv.models import Environment, Mount
from aienv.store import EnvironmentStore


def make_env(workspace: Path) -> Environment:
    return Environment(
        name="demo1",
        agent="claude",
        env={"TOKEN": "abc"},
        workspace=str(workspace),
        mounts=[Mount(source=str(workspace / "src"), alias="src")],
        image="aienv/claude:latest",
        created_at="2026-06-05T00:00:00Z",
    )


def test_save_and_load_environment(aienv_home, tmp_path):
    store = EnvironmentStore()
    env = make_env(tmp_path)

    store.save(env)
    loaded = store.load("demo1")

    assert loaded == env
    assert (aienv_home / "demo1" / "environment.json").exists()


def test_root_override_expands_user_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    store = EnvironmentStore(Path("~/some-aienv-test-root"))

    assert store.root == tmp_path / "some-aienv-test-root"


@pytest.mark.parametrize("name", [".", ".."])
def test_env_dir_rejects_dot_segment_names(name):
    store = EnvironmentStore()

    with pytest.raises(AienvError):
        store.env_dir(name)


@pytest.mark.parametrize("name", [".", ".."])
def test_save_rejects_dot_segment_names(aienv_home, tmp_path, name):
    store = EnvironmentStore()
    env = make_env(tmp_path)
    env.name = name

    with pytest.raises(AienvError):
        store.save(env)

    assert not (aienv_home / "environment.json").exists()
    assert not (aienv_home.parent / "environment.json").exists()


@pytest.mark.parametrize("name", [".", ".."])
def test_delete_rejects_dot_segment_names_without_removing_paths(
    aienv_home, monkeypatch, name
):
    store = EnvironmentStore()
    aienv_home.mkdir(parents=True)
    removed_paths = []

    def fake_rmtree(path):
        removed_paths.append(path)

    monkeypatch.setattr("aienv.store.shutil.rmtree", fake_rmtree)

    with pytest.raises(AienvError):
        store.delete(name)

    assert removed_paths == []


def test_load_missing_environment_raises(aienv_home):
    store = EnvironmentStore()

    with pytest.raises(AienvError):
        store.load("missing")


def test_list_environments_sorts_by_name(aienv_home, tmp_path):
    store = EnvironmentStore()
    store.save(make_env(tmp_path))
    env2 = make_env(tmp_path)
    env2.name = "alpha"
    store.save(env2)

    assert [env.name for env in store.list()] == ["alpha", "demo1"]


def test_delete_environment_removes_directory(aienv_home, tmp_path):
    store = EnvironmentStore()
    store.save(make_env(tmp_path))

    store.delete("demo1")

    assert not (aienv_home / "demo1").exists()


def test_delete_partial_directory_without_state_file_raises(aienv_home):
    store = EnvironmentStore()
    partial_dir = aienv_home / "partial"
    partial_dir.mkdir(parents=True)

    with pytest.raises(AienvError):
        store.delete("partial")

    assert partial_dir.exists()
