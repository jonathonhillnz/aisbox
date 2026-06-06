from pathlib import Path
import tomllib
from typing import Any

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def load_yaml(path: str) -> dict[str, Any]:
    data = yaml.safe_load(read_text(path))
    if not isinstance(data, dict):
        raise TypeError("YAML document must be a mapping")
    return data


def test_public_preview_files_exist():
    assert (ROOT / "LICENSE").is_file()


def test_package_and_repository_use_apache_2_license():
    pyproject = tomllib.loads(read_text("pyproject.toml"))
    assert "setuptools>=77" in pyproject["build-system"]["requires"]
    assert pyproject["project"]["license"] == "Apache-2.0"

    license_text = read_text("LICENSE")
    assert "Apache License" in license_text
    assert "Version 2.0, January 2004" in license_text
    assert "http://www.apache.org/licenses/" in license_text


def test_load_yaml_rejects_non_mapping_documents(tmp_path, monkeypatch):
    (tmp_path / "document.yml").write_text("- item\n", encoding="utf-8")
    monkeypatch.setitem(load_yaml.__globals__, "ROOT", tmp_path)

    with pytest.raises(TypeError, match="mapping"):
        load_yaml("document.yml")


def test_readme_states_preview_and_safety_contract():
    readme = read_text("README.md")

    for text in [
        "Public preview",
        "Python 3.11",
        "Docker",
        "pipx",
        "AISBOX_HOME",
        "Host `~/.claude` and `~/.codex` directories are not copied or mounted.",
        "does not run Docker through `sudo`",
        "Runtime containers are disposable",
        "Claude",
        "Codex",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "Apache-2.0",
    ]:
        assert text in readme

    assert "production-ready" not in readme


def test_readme_documents_all_cli_commands():
    readme = read_text("README.md")

    for command in [
        "aisbox create",
        "aisbox list",
        "aisbox inspect",
        "aisbox delete",
        "aisbox mount",
        "aisbox unmount",
        "aisbox env set",
        "aisbox env unset",
        "aisbox run",
        "aisbox attach",
        "aisbox shell",
        "aisbox rebuild",
        "aisbox set default",
        "aisbox doctor",
    ]:
        assert command in readme


def test_readme_documents_preview_security_boundaries():
    readme = read_text("README.md")
    normalized = readme.lower()

    for text in [
        "environment.json",
        "unencrypted",
        "shell history",
        "outbound network",
        "<state-root>/<name>/files",
        "<state-root>/<name>/config",
        "interactive authentication",
    ]:
        assert text in normalized

    assert "docker receives" in normalized
    assert "local processes" in normalized or "local users" in normalized
    assert "after the container exits" in normalized


def test_readme_places_delete_after_environment_operations():
    readme = read_text("README.md")
    commands = readme.split("## Commands", 1)[1].split("## Known Preview Limitations", 1)[0]
    delete_position = commands.index("aisbox delete -n demo1")

    for command in [
        "aisbox inspect -n demo1",
        "aisbox mount -n demo1",
        "aisbox unmount -n demo1",
        "aisbox env set -n demo1",
        "aisbox env unset -n demo1",
        "aisbox run -n demo1",
        "aisbox attach -n demo1",
        "aisbox shell -n demo1",
        "aisbox rebuild -n demo1",
        "aisbox set default -n demo1",
    ]:
        assert commands.index(command) < delete_position
