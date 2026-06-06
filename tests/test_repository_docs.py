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
