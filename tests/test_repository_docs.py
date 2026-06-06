from pathlib import Path
import tomllib

import yaml


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def load_yaml(path: str) -> object:
    return yaml.safe_load(read_text(path))


def test_public_preview_files_exist():
    for path in [
        "LICENSE",
        "CONTRIBUTING.md",
        "SECURITY.md",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/pull_request_template.md",
        ".github/workflows/ci.yml",
    ]:
        assert (ROOT / path).is_file(), path


def test_package_and_repository_use_apache_2_license():
    pyproject = tomllib.loads(read_text("pyproject.toml"))
    assert pyproject["project"]["license"] == "Apache-2.0"

    license_text = read_text("LICENSE")
    assert "Apache License" in license_text
    assert "Version 2.0, January 2004" in license_text
    assert "http://www.apache.org/licenses/" in license_text
