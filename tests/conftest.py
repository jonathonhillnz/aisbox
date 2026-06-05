import pytest


@pytest.fixture
def aisbox_home(tmp_path, monkeypatch):
    home = tmp_path / "aisbox-home"
    monkeypatch.setenv("AISBOX_HOME", str(home))
    return home
