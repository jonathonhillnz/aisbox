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
    for path in ["LICENSE", "CONTRIBUTING.md", "SECURITY.md"]:
        assert (ROOT / path).is_file()


def test_package_and_repository_use_apache_2_license():
    pyproject = tomllib.loads(read_text("pyproject.toml"))
    assert "setuptools>=77" in pyproject["build-system"]["requires"]
    assert pyproject["project"]["license"] == "Apache-2.0"

    license_text = read_text("LICENSE")
    assert "Apache License" in license_text
    assert "Version 2.0, January 2004" in license_text
    assert "http://www.apache.org/licenses/" in license_text


def test_contributing_policy_covers_preview_workflow():
    contributing = " ".join(read_text("CONTRIBUTING.md").split())

    for text in [
        "public preview",
        "existing issues",
        "substantial",
        "small documentation corrections",
        "[SECURITY.md](SECURITY.md)",
        "not through public issues",
        "Python 3.11",
        "pytest",
        "Docker",
        "credentials",
        "`tmp_path`",
        "`AISBOX_HOME`",
        "`CliRunner`",
        "Mock Docker",
        "expected failures do not emit tracebacks",
        "Link the relevant issue",
        "exact test commands and results",
        "Update `README.md`",
        "`~/.claude`",
        "`~/.codex`",
        "broader host mounts",
        "secrets",
        "automatic `sudo`",
        "generated build output",
        "machine-local files",
        "contributions are licensed under the Apache-2.0 license",
    ]:
        assert text in contributing


def test_security_policy_requires_private_reporting():
    security = " ".join(read_text("SECURITY.md").split())

    for text in [
        "Private vulnerability reporting",
        "Do not open a public issue",
        "default branch",
        "latest tagged preview release, if one exists",
        "Older commits and releases may not receive fixes",
        "affected version, tag, or commit",
        "security boundary and potential impact",
        "Reproduction steps or a proof of concept",
        "suggested mitigation",
        "credentials",
        "tokens",
        "private source code",
        "unrelated host data",
        "best-effort",
        "Keep vulnerability details private",
        "coordinated disclosure",
        "After changing the repository visibility to public",
        "immediately enable GitHub Private vulnerability reporting",
        "before announcing or inviting use of the public preview",
        "`Report a vulnerability`",
    ]:
        assert text in security


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
