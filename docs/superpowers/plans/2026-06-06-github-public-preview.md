# GitHub Public Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare `aisbox` for a GitHub public preview with accurate landing-page documentation, Apache-2.0 licensing, contribution and security guidance, structured issue and pull-request templates, and Python 3.11-3.13 CI.

**Architecture:** Keep user-facing project guidance in root Markdown files and GitHub-specific collaboration configuration under `.github/`. Add a focused repository-contract test module that parses package metadata and GitHub YAML, preventing licensing, safety language, and CI support from silently drifting.

**Tech Stack:** Markdown, GitHub issue forms and Actions YAML, Python 3.11+, pytest, `tomllib`, PyYAML.

---

## File Structure

- Modify `README.md`: replace the minimal README with the public-preview landing page and complete CLI guidance.
- Create `LICENSE`: canonical Apache License 2.0 text.
- Create `CONTRIBUTING.md`: issue-first contribution workflow, development commands, test expectations, and safety guidance.
- Create `SECURITY.md`: private vulnerability reporting instructions and preview support scope.
- Modify `pyproject.toml`: declare `Apache-2.0` and add PyYAML to development dependencies.
- Create `tests/test_repository_docs.py`: enforce public files, metadata, README safety language, YAML validity, and CI matrix.
- Create `.github/ISSUE_TEMPLATE/bug_report.yml`: structured bug intake.
- Create `.github/ISSUE_TEMPLATE/feature_request.yml`: structured feature intake.
- Create `.github/ISSUE_TEMPLATE/config.yml`: disable blank issues and link security guidance.
- Create `.github/pull_request_template.md`: issue, test, documentation, and safety checklist.
- Create `.github/workflows/ci.yml`: pytest matrix for Python 3.11, 3.12, and 3.13.

---

### Task 1: License And Repository Contract Tests

**Files:**
- Modify: `pyproject.toml`
- Create: `LICENSE`
- Create: `tests/test_repository_docs.py`

- [ ] **Step 1: Add failing license and required-file tests**

Create `tests/test_repository_docs.py`:

```python
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
```

- [ ] **Step 2: Add PyYAML to the development environment**

Add this entry to `[project.optional-dependencies].dev` in `pyproject.toml`:

```toml
  "pyyaml>=6,<7",
```

Run:

```bash
.venv/bin/pip install -e ".[dev]"
```

Expected: editable installation succeeds and installs PyYAML 6.x.

- [ ] **Step 3: Run the focused test to verify failure**

Run:

```bash
.venv/bin/pytest tests/test_repository_docs.py -q
```

Expected: FAIL because the required public files and project license metadata do not exist yet.

- [ ] **Step 4: Declare the package license**

Add this field beneath `readme = "README.md"` in `[project]`:

```toml
license = "Apache-2.0"
```

- [ ] **Step 5: Add the canonical Apache License 2.0**

Create `LICENSE` using the complete, unmodified Apache License 2.0 text published at:

```text
https://www.apache.org/licenses/LICENSE-2.0.txt
```

Do not add a copyright header or alter the standard terms.

- [ ] **Step 6: Run the focused license test**

Run:

```bash
.venv/bin/pytest tests/test_repository_docs.py::test_package_and_repository_use_apache_2_license -q
```

Expected: PASS.

- [ ] **Step 7: Commit licensing and contract test setup**

```bash
git add LICENSE pyproject.toml tests/test_repository_docs.py
git commit -m "docs: license aisbox under Apache 2.0"
```

---

### Task 2: Public Preview README

**Files:**
- Modify: `tests/test_repository_docs.py`
- Modify: `README.md`

- [ ] **Step 1: Add failing README contract tests**

Append to `tests/test_repository_docs.py`:

```python
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
```

- [ ] **Step 2: Run the README tests to verify failure**

Run:

```bash
.venv/bin/pytest tests/test_repository_docs.py -q
```

Expected: FAIL because the current README lacks the public-preview, limitations, persistence, and document-link sections.

- [ ] **Step 3: Replace README with the public-preview landing page**

Rewrite `README.md` with these sections and content:

```markdown
# aisbox

`aisbox` runs Claude Code and Codex CLI inside disposable Docker containers,
with explicit persistence for workspaces and agent configuration.

> [!WARNING]
> **Public preview:** `aisbox` is intended for experimentation and feedback.
> Interfaces and workflows may change, and the project is not yet
> production-hardened.

## Safety Model

`aisbox` reduces accidental host exposure by creating isolated agent
environments, but Docker is not a complete security boundary. Review every
workspace and additional directory you mount.

- Environment state is stored under `~/.aisbox/<name>` by default. Set
  `AISBOX_HOME` to relocate it.
- Host `~/.claude` and `~/.codex` directories are not copied or mounted.
- Docker runs as the current user. `aisbox` does not run Docker through `sudo`.
- Runtime containers are disposable. Persistence comes from explicit bind
  mounts and stored environment configuration.
- Environment variable values are stored in the environment configuration.
  Treat the state directory as sensitive.

## Requirements

- Python 3.11 or newer
- Docker Engine available to the current user without `sudo`
- `pipx` for the recommended CLI installation

Check Docker access with:

```bash
docker version
```

## Install From A Checkout

From the repository checkout:

```bash
pipx install .
```

Direct installation from GitHub can be documented once the final repository
URL exists.

## Quick Start

Create an environment with its own managed workspace:

```bash
aisbox create -n demo1 -a claude
```

Or use an existing source directory as the workspace:

```bash
aisbox create -n demo1 -a codex --workspace /path/to/source
```

Set the environment as the default, run a prompt, and inspect the stored
configuration:

```bash
aisbox set default -n demo1
aisbox run -- "summarize this repository"
aisbox inspect
```

Pass `-n demo1` explicitly to override the default for commands that operate on
one environment.

## Supported Agents

| Agent | Create value | Run mode |
| --- | --- | --- |
| Claude Code | `claude` | `claude -p` |
| Codex CLI | `codex` | `codex exec` |

Agent images are built locally during `aisbox create` and `aisbox rebuild`.

## Authentication

Use `aisbox attach -n demo1` to authenticate interactively inside the
environment, or provide API tokens explicitly:

```bash
aisbox create -n demo1 -a claude -e ANTHROPIC_API_KEY=value
aisbox env set -n demo1 OPENAI_API_KEY=value
```

Do not include real tokens in issues, logs, screenshots, or shell history
shared with others. `aisbox inspect` displays environment variable names but
masks their values.

## Workspaces And Persistence

Without `--workspace`, the workspace is
`~/.aisbox/<name>/files`. A supplied workspace is mounted at `/workspace`.

Add and remove extra directory mounts by alias:

```bash
aisbox mount -n demo1 /path/to/dir dir
aisbox unmount -n demo1 dir
```

Additional mounts appear at `/workspace/<alias>`. Mounts are writable and
expose the selected host directory to the agent.

Agent configuration persists under `~/.aisbox/<name>/config`. Runtime
containers use `docker run --rm` and are removed when the command exits.

## Commands

```bash
aisbox create -n demo1 -a claude
aisbox list
aisbox inspect -n demo1
aisbox set default -n demo1
aisbox run -n demo1 -- "summarize this repository"
aisbox attach -n demo1
aisbox shell -n demo1
aisbox rebuild -n demo1
aisbox mount -n demo1 /path/to/dir dir
aisbox unmount -n demo1 dir
aisbox env set -n demo1 KEY=VALUE
aisbox env unset -n demo1 KEY
aisbox doctor
aisbox delete -n demo1 --force
```

Run `aisbox --help` or `aisbox <command> --help` for current option details.

## Known Preview Limitations

- Only Claude Code and Codex CLI are supported.
- Agent images are rebuilt locally and are not pinned to fixed upstream CLI
  versions.
- Mounts and stored environment variables are configured manually.
- Docker-backed integration tests are not part of the normal test suite.
- Compatibility and security response timelines are best-effort during the
  preview.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) before proposing a substantial change.
Report vulnerabilities according to [SECURITY.md](SECURITY.md), never through a
public issue.

Licensed under [Apache-2.0](LICENSE).
```

- [ ] **Step 4: Run README and existing CLI documentation tests**

Run:

```bash
.venv/bin/pytest tests/test_repository_docs.py tests/test_cli_core.py -q
```

Expected: PASS.

- [ ] **Step 5: Compare command names against live CLI help**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m aisbox.cli --help
```

Expected: output lists `create`, `list`, `inspect`, `delete`, `mount`,
`unmount`, `run`, `attach`, `shell`, `rebuild`, `doctor`, `env`, and `set`.

- [ ] **Step 6: Commit the README**

```bash
git add README.md tests/test_repository_docs.py
git commit -m "docs: add public preview README"
```

---

### Task 3: Contribution And Security Policies

**Files:**
- Modify: `tests/test_repository_docs.py`
- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`

- [ ] **Step 1: Add failing policy tests**

Append to `tests/test_repository_docs.py`:

```python
def test_contributing_policy_covers_preview_workflow():
    contributing = read_text("CONTRIBUTING.md")

    for text in [
        "public preview",
        "existing issues",
        "substantial",
        "Python 3.11",
        "pytest",
        "Docker",
        "credentials",
    ]:
        assert text in contributing


def test_security_policy_requires_private_reporting():
    security = read_text("SECURITY.md")

    for text in [
        "Private vulnerability reporting",
        "Do not open a public issue",
        "default branch",
        "best-effort",
    ]:
        assert text in security
```

- [ ] **Step 2: Run policy tests to verify failure**

Run:

```bash
.venv/bin/pytest tests/test_repository_docs.py -q
```

Expected: FAIL because `CONTRIBUTING.md` and `SECURITY.md` do not exist.

- [ ] **Step 3: Add `CONTRIBUTING.md`**

Create `CONTRIBUTING.md`:

```markdown
# Contributing

`aisbox` is a public preview. Bug reports, feature requests, documentation
improvements, and focused code contributions are welcome.

## Before Opening An Issue

Search existing issues before opening a new bug report or feature request. Do
not include credentials, API tokens, private source code, or sensitive host
paths in reports or diagnostic output.

Discuss substantial behavior or design changes in an issue before opening a
pull request. Typo fixes and similarly small documentation corrections do not
need a prior issue.

Security vulnerabilities must follow [SECURITY.md](SECURITY.md) and must not be
reported publicly.

## Development Setup

Use Python 3.11 or newer:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Run the full suite:

```bash
pytest
```

Run a focused test while iterating:

```bash
pytest tests/test_cli_core.py
```

Run the CLI from the checkout:

```bash
python -m aisbox.cli --help
```

## Testing

- Add or update tests for behavior changes.
- Use `tmp_path` and `AISBOX_HOME` for stateful tests.
- Mock Docker subprocess calls unless a change explicitly requires real Docker
  validation.
- Use Typer's `CliRunner` for command output, flags, and exit behavior.
- Preserve clean expected-error output without tracebacks.

## Pull Requests

- Keep changes focused and explain the user-visible behavior.
- Link the discussion issue for substantial changes.
- Include the exact tests run and their result.
- Update `README.md` when commands, flags, installation, or safety guarantees
  change.
- Do not expose host agent configuration, broaden mounts unexpectedly, print
  secrets, or add automatic `sudo` behavior for Docker.
- Ensure generated output, virtual environments, caches, and credentials are
  not committed.

By contributing, you agree that your contribution is licensed under the
repository's Apache-2.0 license.
```

- [ ] **Step 4: Add `SECURITY.md`**

Create `SECURITY.md`:

```markdown
# Security Policy

## Supported Versions

During the public preview, security fixes target the latest code on the
default branch and the latest tagged preview release, if one exists. Older
commits and preview releases may not receive fixes.

## Reporting A Vulnerability

Use GitHub Private vulnerability reporting for this repository. Do not open a
public issue or discussion for a suspected vulnerability.

Include:

- The affected version, tag, or commit.
- The expected security boundary and observed impact.
- Reproduction steps or a minimal proof of concept.
- Any known mitigations or suggested remediation.

Remove credentials, tokens, private source code, and unrelated sensitive host
data from the report.

Acknowledgement, investigation, and remediation timelines are best-effort
during the public preview. Details should remain private until a fix or
coordinated disclosure decision is available.

Repository maintainers must enable Private vulnerability reporting in GitHub's
repository security settings after publication.
```

- [ ] **Step 5: Run policy tests**

Run:

```bash
.venv/bin/pytest tests/test_repository_docs.py -q
```

Expected: only GitHub-template and workflow tests remain failing or absent.

- [ ] **Step 6: Commit public policies**

```bash
git add CONTRIBUTING.md SECURITY.md tests/test_repository_docs.py
git commit -m "docs: add contribution and security policies"
```

---

### Task 4: GitHub Issue And Pull-Request Templates

**Files:**
- Modify: `tests/test_repository_docs.py`
- Create: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Create: `.github/ISSUE_TEMPLATE/feature_request.yml`
- Create: `.github/ISSUE_TEMPLATE/config.yml`
- Create: `.github/pull_request_template.md`

- [ ] **Step 1: Add failing GitHub template tests**

Append to `tests/test_repository_docs.py`:

```python
def test_issue_forms_are_valid_and_have_required_fields():
    bug = load_yaml(".github/ISSUE_TEMPLATE/bug_report.yml")
    feature = load_yaml(".github/ISSUE_TEMPLATE/feature_request.yml")

    assert bug["name"] == "Bug report"
    assert feature["name"] == "Feature request"

    bug_ids = {item.get("id") for item in bug["body"]}
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
    } <= bug_ids

    feature_ids = {item.get("id") for item in feature["body"]}
    assert {"problem", "proposal", "alternatives", "isolation", "context"} <= feature_ids


def test_issue_config_disables_blank_issues_and_links_security_guidance():
    config = load_yaml(".github/ISSUE_TEMPLATE/config.yml")

    assert config["blank_issues_enabled"] is False
    assert config["contact_links"][0]["url"].startswith("https://docs.github.com/")


def test_pull_request_template_covers_review_requirements():
    template = read_text(".github/pull_request_template.md")

    for text in [
        "Linked issue",
        "Tests",
        "Documentation",
        "host agent configuration",
        "mount",
        "secrets",
        "sudo",
    ]:
        assert text in template
```

- [ ] **Step 2: Run template tests to verify failure**

Run:

```bash
.venv/bin/pytest tests/test_repository_docs.py -q
```

Expected: FAIL because the GitHub template files do not exist.

- [ ] **Step 3: Create the bug report issue form**

Create `.github/ISSUE_TEMPLATE/bug_report.yml`:

```yaml
name: Bug report
description: Report reproducible incorrect behavior in aisbox
title: "[Bug]: "
labels:
  - bug
body:
  - type: markdown
    attributes:
      value: |
        Do not include API tokens, credentials, private source code, or sensitive host data.
        Report security vulnerabilities through the private process in SECURITY.md.
  - type: textarea
    id: summary
    attributes:
      label: Summary
      description: Describe the problem concisely.
    validations:
      required: true
  - type: textarea
    id: reproduction
    attributes:
      label: Reproduction steps
      description: Provide the smallest sequence that reproduces the problem.
    validations:
      required: true
  - type: textarea
    id: expected
    attributes:
      label: Expected behavior
    validations:
      required: true
  - type: textarea
    id: actual
    attributes:
      label: Actual behavior
    validations:
      required: true
  - type: input
    id: os
    attributes:
      label: Operating system
      placeholder: Ubuntu 24.04
    validations:
      required: true
  - type: input
    id: python
    attributes:
      label: Python version
      placeholder: Python 3.12.3
    validations:
      required: true
  - type: input
    id: docker
    attributes:
      label: Docker version
      placeholder: Docker version 27.0.0
    validations:
      required: true
  - type: input
    id: aisbox_version
    attributes:
      label: aisbox version or commit
      placeholder: aisbox 0.1.0 or a commit SHA
    validations:
      required: true
  - type: textarea
    id: diagnostics
    attributes:
      label: Sanitized diagnostic output
      description: Include relevant output after removing secrets and sensitive host data.
      render: shell
  - type: checkboxes
    id: sanitized
    attributes:
      label: Sensitive data confirmation
      options:
        - label: I removed credentials, tokens, private source code, and sensitive host data.
          required: true
```

- [ ] **Step 4: Create the feature request issue form**

Create `.github/ISSUE_TEMPLATE/feature_request.yml`:

```yaml
name: Feature request
description: Propose an improvement to aisbox
title: "[Feature]: "
labels:
  - enhancement
body:
  - type: markdown
    attributes:
      value: |
        Search existing issues first. Substantial changes should be discussed before a pull request.
  - type: textarea
    id: problem
    attributes:
      label: Problem or use case
      description: What limitation or workflow problem should be addressed?
    validations:
      required: true
  - type: textarea
    id: proposal
    attributes:
      label: Proposed behavior
      description: Describe the smallest useful change.
    validations:
      required: true
  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives considered
      description: Describe workarounds or alternative designs.
    validations:
      required: true
  - type: textarea
    id: isolation
    attributes:
      label: Relevance to isolated agent environments
      description: Explain how this fits aisbox's isolation and persistence model.
    validations:
      required: true
  - type: textarea
    id: context
    attributes:
      label: Additional context
```

- [ ] **Step 5: Configure issue intake**

Create `.github/ISSUE_TEMPLATE/config.yml`:

```yaml
blank_issues_enabled: false
contact_links:
  - name: Security reporting guidance
    url: https://docs.github.com/en/code-security/security-advisories/working-with-repository-security-advisories/privately-reporting-a-security-vulnerability
    about: Review how to submit a private vulnerability report instead of a public issue.
```

GitHub automatically surfaces the repository's `SECURITY.md` when a user opens
an issue. The external contact link provides GitHub's reporting instructions
without requiring a repository URL before publication.

- [ ] **Step 6: Add the pull-request template**

Create `.github/pull_request_template.md`:

```markdown
## Summary

Describe the change and its user-visible effect.

## Linked Issue

Link the issue discussed before this pull request for substantial changes.
Small documentation corrections do not require a linked issue.

## Tests

List the exact commands run and their results.

## Documentation

Describe documentation changes, or explain why none are needed.

## Safety Checklist

- [ ] This change does not copy or mount host agent configuration unexpectedly.
- [ ] This change does not broaden host directory mounts unexpectedly.
- [ ] This change does not print or commit secrets.
- [ ] This change does not add automatic `sudo` behavior for Docker.
- [ ] Expected user-facing failures remain concise and do not emit tracebacks.
```

- [ ] **Step 7: Run template tests**

Run:

```bash
.venv/bin/pytest tests/test_repository_docs.py -q
```

Expected: PASS for issue-form, issue-config, and pull-request-template tests.

- [ ] **Step 8: Commit GitHub collaboration templates**

```bash
git add .github/ISSUE_TEMPLATE .github/pull_request_template.md tests/test_repository_docs.py
git commit -m "docs: add GitHub collaboration templates"
```

---

### Task 5: Python Test Matrix CI

**Files:**
- Modify: `tests/test_repository_docs.py`
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Add a failing CI workflow test**

Append to `tests/test_repository_docs.py`:

```python
def test_ci_runs_pytest_on_supported_python_versions():
    workflow = load_yaml(".github/workflows/ci.yml")
    test_job = workflow["jobs"]["test"]

    assert test_job["runs-on"] == "ubuntu-latest"
    assert test_job["strategy"]["matrix"]["python-version"] == ["3.11", "3.12", "3.13"]

    rendered_steps = "\n".join(str(step) for step in test_job["steps"])
    assert 'pip install -e ".[dev]"' in rendered_steps
    assert "pytest" in rendered_steps
    assert "docker" not in rendered_steps.lower()
```

- [ ] **Step 2: Run the CI test to verify failure**

Run:

```bash
.venv/bin/pytest tests/test_repository_docs.py::test_ci_runs_pytest_on_supported_python_versions -q
```

Expected: FAIL because `.github/workflows/ci.yml` does not exist.

- [ ] **Step 3: Add the CI workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
  pull_request:

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version:
          - "3.11"
          - "3.12"
          - "3.13"
    steps:
      - name: Check out repository
        uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
      - name: Upgrade pip
        run: python -m pip install --upgrade pip
      - name: Install project
        run: python -m pip install -e ".[dev]"
      - name: Run tests
        run: pytest
```

- [ ] **Step 4: Run the CI workflow test**

Run:

```bash
.venv/bin/pytest tests/test_repository_docs.py::test_ci_runs_pytest_on_supported_python_versions -q
```

Expected: PASS.

- [ ] **Step 5: Commit CI**

```bash
git add .github/workflows/ci.yml tests/test_repository_docs.py
git commit -m "ci: test Python 3.11 through 3.13"
```

---

### Task 6: Full Verification And Public-Launch Check

**Files:**
- Verify all files changed in Tasks 1-5.

- [ ] **Step 1: Run the full test suite**

Run:

```bash
.venv/bin/pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Verify CLI help from the checkout**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m aisbox.cli --help
```

Expected: exit code 0 and the command list matches `README.md`.

- [ ] **Step 3: Validate all GitHub YAML with the structured parser**

Run:

```bash
.venv/bin/python -c 'from pathlib import Path; import yaml; files=sorted(Path(".github").rglob("*.yml")); [yaml.safe_load(path.read_text(encoding="utf-8")) for path in files]; print(f"validated {len(files)} YAML files")'
```

Expected: `validated 4 YAML files`.

- [ ] **Step 4: Check relative Markdown links**

Run:

```bash
.venv/bin/python -c 'from pathlib import Path; required=["LICENSE","CONTRIBUTING.md","SECURITY.md"]; missing=[path for path in required if not Path(path).is_file()]; assert not missing, missing; print("public document links resolve")'
```

Expected: `public document links resolve`.

- [ ] **Step 5: Check formatting and repository status**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only intentional public-preview files are modified.

- [ ] **Step 6: Review the manual GitHub setting**

Confirm `SECURITY.md` states that GitHub Private vulnerability reporting must
be enabled after publication. Do not add a fake security email or claim that a
committed file enables the GitHub setting.

- [ ] **Step 7: Commit any verification corrections**

If verification required corrections:

```bash
git add README.md LICENSE CONTRIBUTING.md SECURITY.md pyproject.toml tests/test_repository_docs.py .github
git commit -m "docs: finalize GitHub public preview"
```

If no corrections were required, do not create an empty commit.
