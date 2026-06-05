import pytest


@pytest.fixture
def aienv_home(tmp_path, monkeypatch):
    home = tmp_path / "aienv-home"
    monkeypatch.setenv("AIENV_HOME", str(home))
    return home
