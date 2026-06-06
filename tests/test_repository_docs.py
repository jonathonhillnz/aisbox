from pathlib import Path
import re
import tomllib
from typing import Any

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_REPORTING_GUIDANCE_URL = (
    "https://docs.github.com/en/code-security/security-advisories/"
    "working-with-repository-security-advisories/"
    "privately-reporting-a-security-vulnerability"
)


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def load_yaml(path: str) -> dict[str, Any]:
    data = yaml.safe_load(read_text(path))
    if not isinstance(data, dict):
        raise TypeError("YAML document must be a mapping")
    return data


def assert_valid_issue_form(form: dict[str, Any]) -> None:
    assert form.keys() <= {
        "name",
        "description",
        "title",
        "labels",
        "assignees",
        "body",
    }
    assert isinstance(form.get("name"), str) and form["name"].strip()
    assert isinstance(form.get("description"), str) and form["description"].strip()
    assert isinstance(form.get("body"), list) and form["body"]
    if "title" in form:
        assert isinstance(form["title"], str)
    for key in ["labels", "assignees"]:
        if key in form:
            values = form[key]
            assert isinstance(values, list)
            assert all(isinstance(value, str) and value.strip() for value in values)
            assert len(values) == len(set(values))

    attribute_keys = {
        "markdown": {"value"},
        "input": {"label", "description", "placeholder", "value"},
        "textarea": {"label", "description", "placeholder", "value", "render"},
        "dropdown": {"label", "description", "multiple", "options"},
        "checkboxes": {"label", "description", "options"},
    }
    field_ids: set[str] = set()
    field_labels: set[str] = set()

    for item in form["body"]:
        assert isinstance(item, dict)
        assert item.keys() <= {"type", "id", "attributes", "validations"}

        item_type = item.get("type")
        assert isinstance(item_type, str)
        assert item_type in attribute_keys
        attributes = item.get("attributes")
        assert isinstance(attributes, dict)
        assert attributes.keys() <= attribute_keys[item_type]

        validations = item.get("validations")
        if validations is not None:
            assert isinstance(validations, dict)
            assert validations.keys() <= {"required"}
            if "required" in validations:
                assert isinstance(validations["required"], bool)

        if item_type == "markdown":
            assert "id" not in item
            assert isinstance(attributes.get("value"), str)
            assert attributes["value"].strip()
            continue

        field_id = item.get("id")
        assert isinstance(field_id, str)
        assert re.fullmatch(r"[A-Za-z0-9_-]+", field_id)
        assert field_id not in field_ids
        field_ids.add(field_id)

        assert isinstance(attributes.get("label"), str)
        assert attributes["label"].strip()
        normalized_label = attributes["label"].strip().casefold()
        assert normalized_label not in field_labels
        field_labels.add(normalized_label)
        for key in {"description", "placeholder", "value", "render"} & attributes.keys():
            assert isinstance(attributes[key], str)

        if item_type == "dropdown":
            if "multiple" in attributes:
                assert isinstance(attributes["multiple"], bool)
            options = attributes.get("options")
            assert isinstance(options, list) and options
            assert all(isinstance(option, str) and option.strip() for option in options)
            normalized_options = [option.strip().casefold() for option in options]
            assert len(normalized_options) == len(set(normalized_options))

        if item_type == "checkboxes":
            options = attributes.get("options")
            assert isinstance(options, list) and options
            option_labels: set[str] = set()
            for option in options:
                assert isinstance(option, dict)
                assert option.keys() <= {"label", "required"}
                assert isinstance(option.get("label"), str) and option["label"].strip()
                normalized_option_label = option["label"].strip().casefold()
                assert normalized_option_label not in option_labels
                option_labels.add(normalized_option_label)
                if "required" in option:
                    assert isinstance(option["required"], bool)


def valid_issue_form() -> dict[str, Any]:
    return {
        "name": "Test form",
        "description": "Test issue form",
        "title": "[Test]: ",
        "labels": ["triage"],
        "assignees": ["maintainer"],
        "body": [
            {
                "type": "textarea",
                "id": "summary",
                "attributes": {"label": "Summary"},
            },
            {
                "type": "checkboxes",
                "id": "confirmation",
                "attributes": {
                    "label": "Confirmation",
                    "options": [{"label": "I confirm"}],
                },
            },
        ],
    }


def test_issue_form_schema_rejects_non_string_title():
    form = valid_issue_form()
    form["title"] = 42

    with pytest.raises(AssertionError):
        assert_valid_issue_form(form)


def test_issue_form_schema_rejects_duplicate_field_labels():
    form = valid_issue_form()
    form["body"][1]["attributes"]["label"] = " summary "

    with pytest.raises(AssertionError):
        assert_valid_issue_form(form)


def test_issue_form_schema_rejects_empty_checkbox_options():
    form = valid_issue_form()
    form["body"][1]["attributes"]["options"] = []

    with pytest.raises(AssertionError):
        assert_valid_issue_form(form)


def test_issue_form_schema_rejects_duplicate_checkbox_option_labels():
    form = valid_issue_form()
    form["body"][1]["attributes"]["options"].append({"label": " i CONFIRM "})

    with pytest.raises(AssertionError):
        assert_valid_issue_form(form)


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
        assert (ROOT / path).is_file()


def test_ci_workflow_tests_supported_python_versions_without_docker():
    workflow = load_yaml(".github/workflows/ci.yml")
    workflow_text = read_text(".github/workflows/ci.yml")

    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["on"] == {"push": None, "pull_request": None}

    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs["test"]
    assert isinstance(job, dict)
    assert job["runs-on"] == "ubuntu-latest"
    assert job["strategy"]["fail-fast"] is False
    assert job["strategy"]["matrix"]["python-version"] == ["3.11", "3.12", "3.13"]

    steps = job["steps"]
    assert all(isinstance(step, dict) for step in steps)
    action_refs = [step["uses"] for step in steps if "uses" in step]
    assert all(
        re.fullmatch(r"actions/(checkout|setup-python)@[0-9a-f]{40}", ref)
        for ref in action_refs
    )
    checkout_ref = "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd"
    setup_python_ref = (
        "actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405"
    )
    assert checkout_ref in action_refs
    assert f"uses: {checkout_ref} # v6.0.2" in workflow_text
    assert f"uses: {setup_python_ref} # v6.2.0" in workflow_text

    setup_python = next(step for step in steps if step.get("uses") == setup_python_ref)
    assert setup_python["with"]["python-version"] == "${{ matrix.python-version }}"
    assert setup_python["with"]["cache"] == "pip"

    run_commands = [step["run"] for step in steps if "run" in step]
    assert "python -m pip install --upgrade pip" in run_commands
    assert 'python -m pip install -e ".[dev]"' in run_commands
    assert "pytest" in run_commands
    assert "container" not in job
    assert "services" not in job
    assert all("docker" not in command.casefold() for command in run_commands)
    assert all(
        "docker" not in step.get("uses", "").casefold()
        for step in steps
        if isinstance(step.get("uses"), str)
    )


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


def test_issue_forms_are_valid_and_have_required_fields():
    bug = load_yaml(".github/ISSUE_TEMPLATE/bug_report.yml")
    feature = load_yaml(".github/ISSUE_TEMPLATE/feature_request.yml")

    assert_valid_issue_form(bug)
    assert_valid_issue_form(feature)

    assert bug["name"] == "Bug report"
    assert bug["description"] == "Report reproducible incorrect behavior in aisbox"
    assert bug["title"] == "[Bug]: "
    assert "labels" not in bug

    bug_fields = {item["id"]: item for item in bug["body"] if "id" in item}
    assert {
        "summary",
        "reproduction",
        "expected",
        "actual",
        "os",
        "python",
        "docker",
        "aisbox_version",
        "diagnostics",
        "sanitized",
    } <= bug_fields.keys()
    for field_id in [
        "summary",
        "reproduction",
        "expected",
        "actual",
        "os",
        "python",
        "docker",
        "aisbox_version",
    ]:
        assert bug_fields[field_id]["validations"]["required"] is True

    assert bug_fields["diagnostics"]["attributes"]["render"] == "shell"
    sanitizer_options = bug_fields["sanitized"]["attributes"]["options"]
    assert any(option.get("required") is True for option in sanitizer_options)

    bug_guidance = " ".join(
        item["attributes"]["value"]
        for item in bug["body"]
        if item["type"] == "markdown"
    )
    for text in [
        "API tokens",
        "credentials",
        "private source",
        "sensitive host data",
        "Security policy",
        "issue chooser",
        "private reporting guidance",
    ]:
        assert text in bug_guidance

    assert feature["name"] == "Feature request"
    assert feature["description"] == "Propose an improvement to aisbox"
    assert feature["title"] == "[Feature]: "
    assert "labels" not in feature

    feature_fields = {item["id"]: item for item in feature["body"] if "id" in item}
    assert {"problem", "proposal", "alternatives", "isolation", "context"} <= (
        feature_fields.keys()
    )
    for field_id in ["problem", "proposal", "alternatives", "isolation"]:
        assert feature_fields[field_id]["validations"]["required"] is True
    assert "validations" not in feature_fields["context"]

    feature_guidance = " ".join(
        item["attributes"]["value"]
        for item in feature["body"]
        if item["type"] == "markdown"
    )
    assert "Search existing issues first" in feature_guidance
    assert "discussed before a pull request" in feature_guidance


def test_issue_config_disables_blank_issues_and_links_security_guidance():
    config = load_yaml(".github/ISSUE_TEMPLATE/config.yml")

    assert config["blank_issues_enabled"] is False
    security_link = config["contact_links"][0]
    assert security_link["name"] == "Security reporting guidance"
    assert security_link["url"] == PRIVATE_REPORTING_GUIDANCE_URL
    assert "private" in security_link["about"]
    assert "public issue" in security_link["about"]


def test_pull_request_template_covers_review_requirements():
    template = read_text(".github/pull_request_template.md")

    for text in [
        "Summary",
        "Linked Issue",
        "substantial",
        "Small documentation corrections",
        "Tests",
        "exact commands",
        "results",
        "Documentation",
        "Host `~/.claude` and `~/.codex` are not copied or mounted",
        "additional host directory mounts",
        "mount",
        "secrets",
        "sudo",
        "concise",
        "tracebacks",
    ]:
        assert text in template
    assert "unexpectedly" not in template


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


def test_readme_documents_platform_scope_and_managed_state_permissions():
    normalized = " ".join(read_text("README.md").lower().split())

    assert "posix" in normalized
    assert "linux and macos" in normalized
    assert "native windows hosts are not supported during the public preview" in normalized
    assert "0700" in normalized
    assert "0600" in normalized
    assert "managed state directories" in normalized
    assert "managed state files" in normalized
    assert "stored unencrypted" in normalized


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
