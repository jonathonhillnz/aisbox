# GitHub Public Preview Design

## Purpose

Prepare `aisbox` for an eventual public GitHub launch without presenting the
project as production-ready. The repository will be usable by early adopters,
accept bug reports and feature requests, and welcome pull requests under a
lightweight issue-first policy.

The public documentation must accurately reflect the implemented CLI and the
project's existing safety contract.

## Public Posture

`aisbox` will be described as a public preview:

- It is suitable for experimentation and feedback.
- Interfaces and workflows may change during the preview.
- It is not yet production-hardened.
- Public issues may be used for bugs and feature requests.
- Pull requests are welcome. Substantial changes should be discussed in an
  issue first; minor corrections do not require a prior issue.
- Security vulnerabilities must not be reported in public issues.

## Documentation Set

### README

Expand `README.md` into the primary landing page with:

- A concise description of the project.
- A visible public-preview notice.
- The safety model and explicit isolation boundaries.
- Requirements: Python 3.11 or newer, Docker usable by the current user
  without `sudo`, and `pipx` for the documented installation path.
- A working checkout-based installation command. Do not add a fictional
  GitHub owner or repository URL; direct GitHub installation can be documented
  after the repository exists.
- A quick-start workflow covering environment creation, selecting a default
  environment, running an agent, and inspecting the environment.
- Supported agents: Claude and Codex.
- Command examples for the implemented CLI.
- Authentication guidance for interactive login and explicit API tokens.
- State storage, workspace mounts, additional mounts, and environment
  variables.
- Known preview limitations.
- Links to contribution, security, and license documents.

The README must not claim that Docker provides a complete security boundary.
It must preserve these explicit guarantees:

- State defaults to `~/.aisbox/<name>` and can be relocated with
  `AISBOX_HOME`.
- Host `~/.claude` and `~/.codex` directories are not copied or mounted.
- Docker runs as the current user; `aisbox` does not add automatic `sudo`
  behavior.
- Runtime containers are disposable. Persistence comes from configured bind
  mounts and stored environment state.

### License

Add the standard Apache License 2.0 text in `LICENSE`.

Set the package metadata license to `Apache-2.0` so built distributions and
package indexes expose the same licensing decision as the repository.

### Contributing Guide

Add `CONTRIBUTING.md` with:

- The public-preview contribution posture.
- A request to search existing issues before opening a new one.
- An issue-first requirement for substantial behavior changes.
- An exception for typo fixes and similarly small corrections.
- Development environment setup using Python 3.11 or newer.
- Focused and full pytest commands.
- Guidance to mock Docker subprocess calls in normal tests.
- Pull-request expectations for scope, tests, documentation, and safety.
- A reminder not to include credentials, tokens, or sensitive host data.

### Security Policy

Add `SECURITY.md` with:

- A statement that supported preview releases are the latest code on the
  default branch and the latest tagged preview release, if one exists.
- Instructions to use GitHub private vulnerability reporting.
- A prohibition on reporting vulnerabilities through public issues.
- The information requested in a private report: affected version or commit,
  impact, reproduction details, and suggested mitigation when available.
- A statement that response and remediation timelines are best-effort during
  the public preview.

The GitHub repository owner must enable private vulnerability reporting in the
repository settings after publication; this setting cannot be enabled by a
committed file.

## GitHub Collaboration

### Issue Forms

Create `.github/ISSUE_TEMPLATE/bug_report.yml` with required fields for:

- Problem summary.
- Reproduction steps.
- Expected behavior.
- Actual behavior.
- Operating system.
- Python version.
- Docker version.
- `aisbox` version or commit.
- Sanitized diagnostic output.
- Confirmation that secrets and sensitive host data were removed.

Create `.github/ISSUE_TEMPLATE/feature_request.yml` with fields for:

- The problem or use case.
- Proposed behavior.
- Alternatives considered.
- Relevance to isolated agent environments.
- Additional context.

Create `.github/ISSUE_TEMPLATE/config.yml` to:

- Disable blank issues.
- Provide a security-policy contact link.

### Pull-Request Template

Create `.github/pull_request_template.md` with:

- A concise summary.
- A linked issue field for substantial changes.
- Test evidence.
- Documentation impact.
- A safety checklist confirming that the change does not unexpectedly expose
  host agent configuration, broaden mounts, print secrets, or introduce
  automatic Docker privilege escalation.

The template will state that small documentation corrections do not require a
linked issue.

## Continuous Integration

Create `.github/workflows/ci.yml`.

The workflow will run on pushes and pull requests using Ubuntu with a Python
matrix of:

- Python 3.11
- Python 3.12
- Python 3.13

Each job will:

1. Check out the repository.
2. Install the matrix Python version.
3. Upgrade `pip`.
4. Install the project with `pip install -e ".[dev]"`.
5. Run `pytest`.

The workflow will not require a Docker daemon. Existing tests mock Docker
subprocess behavior, and this preparation will not add Docker integration
tests, dependency update automation, or release workflows.

## Verification

Implementation verification will include:

- Running the full pytest suite locally.
- Running `python -m aisbox.cli --help` to compare the README command
  reference with the implemented CLI.
- Parsing the workflow and issue-form YAML with an available structured YAML
  parser, or reviewing it with a purpose-built validation command if one is
  already available in the development environment.
- Checking repository links and relative paths.
- Reviewing all public text for preview status, secret-handling guidance, and
  consistency with the safety contract.

## Out Of Scope

The public-preview preparation will not add:

- Release or package-publishing workflows.
- Dependabot configuration.
- A changelog or formal roadmap.
- A code of conduct.
- Docker-backed integration tests.
- Support guarantees or fixed security response times.
- Claims of production readiness or complete containment.
