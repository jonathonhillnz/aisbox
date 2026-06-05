# aisbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI named `aisbox` that creates isolated Docker-backed AI agent environments for Claude and Codex.

**Architecture:** The CLI is a Typer application with thin command handlers. Persistent environment state is stored as JSON under an injectable home directory, Docker integration is isolated behind command-building and subprocess functions, and agent-specific behavior is captured in data-only agent definitions.

**Tech Stack:** Python 3.11+, Typer, pytest, subprocess, dataclasses, pathlib, json.

---

## File Structure

- Create `pyproject.toml`: package metadata, dependencies, console script, pytest config.
- Create `README.md`: install and v1 usage documentation.
- Create `src/aisbox/__init__.py`: package version.
- Create `src/aisbox/cli.py`: Typer CLI, argument parsing, command output.
- Create `src/aisbox/commands.py`: command orchestration using store, agents, and Docker modules.
- Create `src/aisbox/models.py`: dataclasses for environment state, mounts, and agent definitions.
- Create `src/aisbox/validation.py`: name, env var, mount alias, and path validation.
- Create `src/aisbox/store.py`: JSON persistence under `~/.aisbox` or test override.
- Create `src/aisbox/agents.py`: Claude and Codex definitions plus Dockerfile templates.
- Create `src/aisbox/docker.py`: Docker command construction and subprocess execution.
- Create `src/aisbox/errors.py`: user-facing exception types.
- Create `tests/conftest.py`: shared temporary home fixtures.
- Create `tests/test_validation.py`: validation unit tests.
- Create `tests/test_store.py`: persistence unit tests.
- Create `tests/test_agents.py`: agent lookup and Dockerfile tests.
- Create `tests/test_docker.py`: Docker command construction tests.
- Create `tests/test_cli_core.py`: create, list, inspect, delete CLI tests.
- Create `tests/test_cli_mutation.py`: mount, unmount, env set, env unset tests.
- Create `tests/test_cli_runtime.py`: run, attach, shell, rebuild tests with mocked subprocess.
- Create `tests/test_doctor.py`: doctor diagnostics tests.

## Shared Implementation Rules

- Keep command handlers small. Validation and state mutation belong outside `cli.py`.
- All Docker subprocess calls must pass argument lists, not shell strings.
- Do not prefix Docker commands with `sudo`. Docker must be usable by the current user.
- Tests must not require Docker, Claude, Codex, network access, or real credentials.
- Use `AISBOX_HOME` as a testable override for the state root. Default to `~/.aisbox`.
- Never read, copy, or mount host `~/.claude` or `~/.codex`.
- Use ASCII in source files.

---

### Task 1: Package Scaffold And CLI Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/aisbox/__init__.py`
- Create: `src/aisbox/cli.py`
- Create: `src/aisbox/errors.py`
- Create: `tests/test_cli_core.py`

- [ ] **Step 1: Write failing CLI smoke tests**

Create `tests/test_cli_core.py`:

```python
from typer.testing import CliRunner

from aisbox.cli import app


runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "aisbox" in result.stdout


def test_list_empty_environment_home(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "No environments found" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_cli_core.py -v
```

Expected: FAIL because the package and CLI do not exist yet.

- [ ] **Step 3: Add package metadata**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "aisbox"
version = "0.1.0"
description = "Run AI coding agents inside isolated Docker environments"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "typer>=0.12,<1.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8,<9",
]

[project.scripts]
aisbox = "aisbox.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

Create `README.md`:

```markdown
# aisbox

`aisbox` runs AI coding agents inside isolated Docker environments.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Install From This Repository

```bash
pipx install .
```
```

- [ ] **Step 4: Add minimal CLI**

Create `src/aisbox/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `src/aisbox/errors.py`:

```python
class AisboxError(Exception):
    """Base class for user-facing aisbox errors."""
```

Create `src/aisbox/cli.py`:

```python
from __future__ import annotations

from typing import Optional

import typer

from aisbox import __version__


app = typer.Typer(no_args_is_help=True)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"aisbox {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    return None


@app.command("list")
def list_envs() -> None:
    typer.echo("No environments found")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
pytest tests/test_cli_core.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml README.md src/aisbox tests/test_cli_core.py
git commit -m "feat: scaffold aisbox cli package"
```

---

### Task 2: Validation And State Models

**Files:**
- Create: `src/aisbox/models.py`
- Create: `src/aisbox/validation.py`
- Create: `tests/test_validation.py`

- [ ] **Step 1: Write failing validation tests**

Create `tests/test_validation.py`:

```python
import pytest

from aisbox.errors import AisboxError
from aisbox.validation import (
    parse_env_assignment,
    validate_env_name,
    validate_mount_alias,
)


@pytest.mark.parametrize("name", ["demo1", "demo-1", "demo_1", "demo.1"])
def test_validate_env_name_accepts_safe_names(name):
    assert validate_env_name(name) == name


@pytest.mark.parametrize("name", ["", "../demo", "demo/name", "demo name", "$demo"])
def test_validate_env_name_rejects_unsafe_names(name):
    with pytest.raises(AisboxError):
        validate_env_name(name)


def test_parse_env_assignment():
    assert parse_env_assignment("TOKEN=abc=123") == ("TOKEN", "abc=123")


@pytest.mark.parametrize("assignment", ["TOKEN", "=value", "BAD-KEY=value", ""])
def test_parse_env_assignment_rejects_invalid_values(assignment):
    with pytest.raises(AisboxError):
        parse_env_assignment(assignment)


@pytest.mark.parametrize("alias", ["src", "data_1", "repo-2", "repo.3"])
def test_validate_mount_alias_accepts_relative_name(alias):
    assert validate_mount_alias(alias) == alias


@pytest.mark.parametrize("alias", ["", "/src", "../src", "src/repo", "src..repo"])
def test_validate_mount_alias_rejects_path_like_values(alias):
    with pytest.raises(AisboxError):
        validate_mount_alias(alias)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_validation.py -v
```

Expected: FAIL because validation functions do not exist.

- [ ] **Step 3: Add models and validation**

Create `src/aisbox/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Mount:
    source: str
    alias: str


@dataclass
class Environment:
    name: str
    agent: str
    env: dict[str, str]
    workspace: str
    mounts: list[Mount]
    image: str
    created_at: str


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    image: str
    config_path: str
    dockerfile: str
    run_command: list[str]
    attach_command: list[str]
    shell_command: list[str] = field(default_factory=lambda: ["/bin/bash"])
```

Create `src/aisbox/validation.py`:

```python
from __future__ import annotations

import re

from aisbox.errors import AisboxError


ENV_NAME_RE = re.compile(r"^[a-zA-Z0-9_.-]+$")
ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_env_name(name: str) -> str:
    if not ENV_NAME_RE.match(name):
        raise AisboxError("Environment name must match [a-zA-Z0-9_.-]+")
    return name


def parse_env_assignment(assignment: str) -> tuple[str, str]:
    if "=" not in assignment:
        raise AisboxError("Environment variable must be KEY=VALUE")
    key, value = assignment.split("=", 1)
    if not key or not ENV_KEY_RE.match(key):
        raise AisboxError("Environment variable key must match [A-Za-z_][A-Za-z0-9_]*")
    return key, value


def validate_mount_alias(alias: str) -> str:
    if not alias or alias.startswith("/") or "/" in alias or ".." in alias:
        raise AisboxError("Mount alias must be a relative name under /workspace")
    return validate_env_name(alias)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/test_validation.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/aisbox/models.py src/aisbox/validation.py tests/test_validation.py
git commit -m "feat: add validation and state models"
```

---

### Task 3: Environment Store

**Files:**
- Create: `src/aisbox/store.py`
- Create: `tests/conftest.py`
- Create: `tests/test_store.py`

- [ ] **Step 1: Write failing store tests**

Create `tests/conftest.py`:

```python
import pytest


@pytest.fixture
def aisbox_home(tmp_path, monkeypatch):
    home = tmp_path / "aisbox-home"
    monkeypatch.setenv("AISBOX_HOME", str(home))
    return home
```

Create `tests/test_store.py`:

```python
from pathlib import Path

import pytest

from aisbox.errors import AisboxError
from aisbox.models import Environment, Mount
from aisbox.store import EnvironmentStore


def make_env(workspace: Path) -> Environment:
    return Environment(
        name="demo1",
        agent="claude",
        env={"TOKEN": "abc"},
        workspace=str(workspace),
        mounts=[Mount(source=str(workspace / "src"), alias="src")],
        image="aisbox/claude:latest",
        created_at="2026-06-05T00:00:00Z",
    )


def test_save_and_load_environment(aisbox_home, tmp_path):
    store = EnvironmentStore()
    env = make_env(tmp_path)

    store.save(env)
    loaded = store.load("demo1")

    assert loaded == env
    assert (aisbox_home / "demo1" / "environment.json").exists()


def test_load_missing_environment_raises(aisbox_home):
    store = EnvironmentStore()

    with pytest.raises(AisboxError):
        store.load("missing")


def test_list_environments_sorts_by_name(aisbox_home, tmp_path):
    store = EnvironmentStore()
    store.save(make_env(tmp_path))
    env2 = make_env(tmp_path)
    env2.name = "alpha"
    store.save(env2)

    assert [env.name for env in store.list()] == ["alpha", "demo1"]


def test_delete_environment_removes_directory(aisbox_home, tmp_path):
    store = EnvironmentStore()
    store.save(make_env(tmp_path))

    store.delete("demo1")

    assert not (aisbox_home / "demo1").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_store.py -v
```

Expected: FAIL because `EnvironmentStore` does not exist.

- [ ] **Step 3: Implement JSON store**

Create `src/aisbox/store.py`:

```python
from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict
from pathlib import Path

from aisbox.errors import AisboxError
from aisbox.models import Environment, Mount
from aisbox.validation import validate_env_name


class EnvironmentStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(os.environ.get("AISBOX_HOME", "~/.aisbox")).expanduser()

    def env_dir(self, name: str) -> Path:
        return self.root / validate_env_name(name)

    def config_dir(self, name: str, agent: str) -> Path:
        return self.env_dir(name) / "config" / agent

    def default_workspace(self, name: str) -> Path:
        return self.env_dir(name) / "files"

    def exists(self, name: str) -> bool:
        return (self.env_dir(name) / "environment.json").exists()

    def create_dirs(self, name: str, agent: str) -> None:
        self.config_dir(name, agent).mkdir(parents=True, exist_ok=True)
        self.default_workspace(name).mkdir(parents=True, exist_ok=True)

    def save(self, env: Environment) -> None:
        env_dir = self.env_dir(env.name)
        env_dir.mkdir(parents=True, exist_ok=True)
        payload = asdict(env)
        (env_dir / "environment.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def load(self, name: str) -> Environment:
        path = self.env_dir(name) / "environment.json"
        if not path.exists():
            raise AisboxError(f"Environment does not exist: {name}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["mounts"] = [Mount(**mount) for mount in payload.get("mounts", [])]
        return Environment(**payload)

    def list(self) -> list[Environment]:
        if not self.root.exists():
            return []
        envs = []
        for path in self.root.iterdir():
            state_file = path / "environment.json"
            if state_file.exists():
                envs.append(self.load(path.name))
        return sorted(envs, key=lambda env: env.name)

    def delete(self, name: str) -> None:
        path = self.env_dir(name)
        if not path.exists():
            raise AisboxError(f"Environment does not exist: {name}")
        shutil.rmtree(path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/test_store.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/aisbox/store.py tests/conftest.py tests/test_store.py
git commit -m "feat: persist environment state"
```

---

### Task 4: Agent Definitions And Docker Build

**Files:**
- Create: `src/aisbox/agents.py`
- Create: `src/aisbox/docker.py`
- Create: `tests/test_agents.py`
- Create: `tests/test_docker.py`

- [ ] **Step 1: Write failing agent and Docker tests**

Create `tests/test_agents.py`:

```python
import pytest

from aisbox.agents import get_agent, supported_agents
from aisbox.errors import AisboxError


def test_supported_agents_include_claude_and_codex():
    assert supported_agents() == ["claude", "codex"]


def test_get_agent_returns_claude_definition():
    agent = get_agent("claude")

    assert agent.name == "claude"
    assert agent.image == "aisbox/claude:latest"
    assert agent.config_path == "/home/aisbox/.claude"
    assert "npm install -g @anthropic-ai/claude-code" in agent.dockerfile


def test_get_agent_rejects_unknown_agent():
    with pytest.raises(AisboxError):
        get_agent("unknown")
```

Create `tests/test_docker.py`:

```python
from pathlib import Path
from unittest.mock import Mock

from aisbox.agents import get_agent
from aisbox.docker import build_image, docker_available
from aisbox.models import Environment


def test_build_image_invokes_docker_build_with_stdin(tmp_path):
    runner = Mock()
    agent = get_agent("claude")

    build_image(agent, runner=runner)

    runner.assert_called_once()
    args, kwargs = runner.call_args
    assert args[0] == ["docker", "build", "-t", "aisbox/claude:latest", "-"]
    assert kwargs["input"] == agent.dockerfile
    assert kwargs["text"] is True
    assert kwargs["check"] is True


def test_docker_available_returns_false_when_command_fails():
    def failing_runner(command, **kwargs):
        raise FileNotFoundError()

    assert docker_available(runner=failing_runner) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_agents.py tests/test_docker.py -v
```

Expected: FAIL because agent and Docker modules do not exist.

- [ ] **Step 3: Add agent definitions**

Create `src/aisbox/agents.py`:

```python
from __future__ import annotations

from aisbox.errors import AisboxError
from aisbox.models import AgentDefinition


BASE_DOCKERFILE_PREFIX = """FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \\
    && apt-get install -y --no-install-recommends \\
       bash ca-certificates curl git nodejs npm \\
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m -s /bin/bash aisbox
USER aisbox
WORKDIR /workspace
"""


AGENTS = {
    "claude": AgentDefinition(
        name="claude",
        image="aisbox/claude:latest",
        config_path="/home/aisbox/.claude",
        dockerfile=BASE_DOCKERFILE_PREFIX
        + "RUN npm install -g @anthropic-ai/claude-code\n",
        run_command=["claude", "-p"],
        attach_command=["claude"],
    ),
    "codex": AgentDefinition(
        name="codex",
        image="aisbox/codex:latest",
        config_path="/home/aisbox/.codex",
        dockerfile=BASE_DOCKERFILE_PREFIX + "RUN npm install -g @openai/codex\n",
        run_command=["codex", "exec"],
        attach_command=["codex"],
    ),
}


def supported_agents() -> list[str]:
    return sorted(AGENTS)


def get_agent(name: str) -> AgentDefinition:
    try:
        return AGENTS[name]
    except KeyError as exc:
        raise AisboxError(f"Unsupported agent: {name}") from exc
```

- [ ] **Step 4: Add Docker build helpers**

Create `src/aisbox/docker.py`:

```python
from __future__ import annotations

import subprocess
from collections.abc import Callable

from aisbox.models import AgentDefinition


Runner = Callable[..., subprocess.CompletedProcess]


def default_runner(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, **kwargs)


def build_image(agent: AgentDefinition, runner: Runner = default_runner) -> None:
    runner(
        ["docker", "build", "-t", agent.image, "-"],
        input=agent.dockerfile,
        text=True,
        check=True,
    )


def docker_available(runner: Runner = default_runner) -> bool:
    try:
        runner(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    return True
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
pytest tests/test_agents.py tests/test_docker.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/aisbox/agents.py src/aisbox/docker.py tests/test_agents.py tests/test_docker.py
git commit -m "feat: define agents and docker image builds"
```

---

### Task 5: Core Environment Commands

**Files:**
- Create: `src/aisbox/commands.py`
- Modify: `src/aisbox/cli.py`
- Modify: `tests/test_cli_core.py`

- [ ] **Step 1: Extend failing CLI tests**

Replace `tests/test_cli_core.py` with:

```python
from typer.testing import CliRunner

from aisbox.cli import app


runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "aisbox" in result.stdout


def test_list_empty_environment_home(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "No environments found" in result.stdout


def test_create_list_and_inspect_environment(tmp_path, monkeypatch):
    home = tmp_path / "aisbox-home"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("AISBOX_HOME", str(home))
    monkeypatch.setattr("aisbox.commands.build_image", lambda agent: None)

    create = runner.invoke(
        app,
        [
            "create",
            "-n",
            "demo1",
            "-a",
            "claude",
            "-e",
            "TOKEN=abc",
            "--workspace",
            str(workspace),
        ],
    )
    listed = runner.invoke(app, ["list"])
    inspected = runner.invoke(app, ["inspect", "-n", "demo1"])

    assert create.exit_code == 0
    assert "Created demo1" in create.stdout
    assert listed.exit_code == 0
    assert "demo1" in listed.stdout
    assert "claude" in listed.stdout
    assert inspected.exit_code == 0
    assert "workspace" in inspected.stdout
    assert "TOKEN" in inspected.stdout
    assert "abc" not in inspected.stdout


def test_delete_environment_with_force(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    monkeypatch.setattr("aisbox.commands.build_image", lambda agent: None)
    runner.invoke(app, ["create", "-n", "demo1", "-a", "claude"])

    result = runner.invoke(app, ["delete", "-n", "demo1", "--force"])

    assert result.exit_code == 0
    assert "Deleted demo1" in result.stdout
    assert runner.invoke(app, ["list"]).stdout.strip() == "No environments found"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_cli_core.py -v
```

Expected: FAIL because create, inspect, and delete are not implemented.

- [ ] **Step 3: Implement command orchestration**

Create `src/aisbox/commands.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from aisbox.agents import get_agent
from aisbox.docker import build_image
from aisbox.errors import AisboxError
from aisbox.models import Environment
from aisbox.store import EnvironmentStore
from aisbox.validation import parse_env_assignment, validate_env_name


def create_environment(
    name: str,
    agent_name: str,
    env_assignments: list[str],
    workspace: str | None,
    store: EnvironmentStore | None = None,
) -> Environment:
    store = store or EnvironmentStore()
    name = validate_env_name(name)
    if store.exists(name):
        raise AisboxError(f"Environment already exists: {name}")
    agent = get_agent(agent_name)
    env = dict(parse_env_assignment(item) for item in env_assignments)
    store.create_dirs(name, agent.name)
    workspace_path = Path(workspace).expanduser().resolve() if workspace else store.default_workspace(name)
    if not workspace_path.exists() or not workspace_path.is_dir():
        raise AisboxError(f"Workspace path does not exist: {workspace_path}")
    created = Environment(
        name=name,
        agent=agent.name,
        env=env,
        workspace=str(workspace_path),
        mounts=[],
        image=agent.image,
        created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    build_image(agent)
    store.save(created)
    return created


def list_environments(store: EnvironmentStore | None = None) -> list[Environment]:
    return (store or EnvironmentStore()).list()


def inspect_environment(name: str, store: EnvironmentStore | None = None) -> Environment:
    return (store or EnvironmentStore()).load(name)


def delete_environment(name: str, store: EnvironmentStore | None = None) -> None:
    (store or EnvironmentStore()).delete(name)
```

- [ ] **Step 4: Update CLI commands**

Replace `src/aisbox/cli.py` with:

```python
from __future__ import annotations

from typing import Optional

import typer

from aisbox import __version__
from aisbox.commands import (
    create_environment,
    delete_environment,
    inspect_environment,
    list_environments,
)
from aisbox.errors import AisboxError


app = typer.Typer(no_args_is_help=True)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"aisbox {__version__}")
        raise typer.Exit()


def handle_error(exc: AisboxError) -> None:
    typer.echo(f"Error: {exc}", err=True)
    raise typer.Exit(code=1)


@app.callback()
def root(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    return None


@app.command("create")
def create(
    name: str = typer.Option(..., "-n", "--name"),
    agent: str = typer.Option(..., "-a", "--agent"),
    env: list[str] = typer.Option([], "-e", "--env"),
    workspace: str | None = typer.Option(None, "--workspace"),
) -> None:
    try:
        created = create_environment(name, agent, env, workspace)
    except AisboxError as exc:
        handle_error(exc)
    typer.echo(f"Created {created.name}")


@app.command("list")
def list_envs() -> None:
    envs = list_environments()
    if not envs:
        typer.echo("No environments found")
        return
    for env in envs:
        typer.echo(f"{env.name}\t{env.agent}\t{env.workspace}")


@app.command("inspect")
def inspect(name: str = typer.Option(..., "-n", "--name")) -> None:
    try:
        env = inspect_environment(name)
    except AisboxError as exc:
        handle_error(exc)
    typer.echo(f"name: {env.name}")
    typer.echo(f"agent: {env.agent}")
    typer.echo(f"workspace: {env.workspace}")
    typer.echo(f"image: {env.image}")
    typer.echo("env:")
    for key in sorted(env.env):
        typer.echo(f"  {key}=<set>")
    typer.echo("mounts:")
    for mount in env.mounts:
        typer.echo(f"  {mount.alias}: {mount.source}")


@app.command("delete")
def delete(
    name: str = typer.Option(..., "-n", "--name"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    if not force and not typer.confirm(f"Delete environment {name}"):
        raise typer.Exit(code=1)
    try:
        delete_environment(name)
    except AisboxError as exc:
        handle_error(exc)
    typer.echo(f"Deleted {name}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
pytest tests/test_cli_core.py tests/test_store.py tests/test_validation.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/aisbox/commands.py src/aisbox/cli.py tests/test_cli_core.py
git commit -m "feat: add core environment commands"
```

---

### Task 6: Mount And Environment Variable Mutation

**Files:**
- Modify: `src/aisbox/commands.py`
- Modify: `src/aisbox/cli.py`
- Create: `tests/test_cli_mutation.py`

- [ ] **Step 1: Write failing mutation tests**

Create `tests/test_cli_mutation.py`:

```python
from typer.testing import CliRunner

from aisbox.cli import app


runner = CliRunner()


def create_demo(monkeypatch):
    monkeypatch.setattr("aisbox.commands.build_image", lambda agent: None)
    result = runner.invoke(app, ["create", "-n", "demo1", "-a", "claude"])
    assert result.exit_code == 0


def test_mount_and_unmount(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    source = tmp_path / "source"
    source.mkdir()
    create_demo(monkeypatch)

    mounted = runner.invoke(app, ["mount", "-n", "demo1", str(source), "src"])
    inspected = runner.invoke(app, ["inspect", "-n", "demo1"])
    unmounted = runner.invoke(app, ["unmount", "-n", "demo1", "src"])
    inspected_again = runner.invoke(app, ["inspect", "-n", "demo1"])

    assert mounted.exit_code == 0
    assert "Mounted src" in mounted.stdout
    assert str(source.resolve()) in inspected.stdout
    assert unmounted.exit_code == 0
    assert "Unmounted src" in unmounted.stdout
    assert "src:" not in inspected_again.stdout


def test_env_set_and_unset(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    create_demo(monkeypatch)

    set_result = runner.invoke(app, ["env", "set", "-n", "demo1", "TOKEN=abc"])
    inspected = runner.invoke(app, ["inspect", "-n", "demo1"])
    unset_result = runner.invoke(app, ["env", "unset", "-n", "demo1", "TOKEN"])
    inspected_again = runner.invoke(app, ["inspect", "-n", "demo1"])

    assert set_result.exit_code == 0
    assert "Set TOKEN" in set_result.stdout
    assert "TOKEN=<set>" in inspected.stdout
    assert "abc" not in inspected.stdout
    assert unset_result.exit_code == 0
    assert "Unset TOKEN" in unset_result.stdout
    assert "TOKEN=<set>" not in inspected_again.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_cli_mutation.py -v
```

Expected: FAIL because mutation commands do not exist.

- [ ] **Step 3: Add mutation functions**

Append to `src/aisbox/commands.py`:

```python
from aisbox.models import Mount
from aisbox.validation import validate_mount_alias


def add_mount(
    name: str,
    source: str,
    alias: str,
    store: EnvironmentStore | None = None,
) -> Mount:
    store = store or EnvironmentStore()
    env = store.load(name)
    alias = validate_mount_alias(alias)
    source_path = Path(source).expanduser().resolve()
    if not source_path.exists() or not source_path.is_dir():
        raise AisboxError(f"Mount source path does not exist: {source_path}")
    if any(mount.alias == alias for mount in env.mounts):
        raise AisboxError(f"Mount alias already exists: {alias}")
    mount = Mount(source=str(source_path), alias=alias)
    env.mounts.append(mount)
    store.save(env)
    return mount


def remove_mount(name: str, alias: str, store: EnvironmentStore | None = None) -> None:
    store = store or EnvironmentStore()
    env = store.load(name)
    alias = validate_mount_alias(alias)
    original_count = len(env.mounts)
    env.mounts = [mount for mount in env.mounts if mount.alias != alias]
    if len(env.mounts) == original_count:
        raise AisboxError(f"Mount alias does not exist: {alias}")
    store.save(env)


def set_env_var(
    name: str,
    assignment: str,
    store: EnvironmentStore | None = None,
) -> str:
    store = store or EnvironmentStore()
    env = store.load(name)
    key, value = parse_env_assignment(assignment)
    env.env[key] = value
    store.save(env)
    return key


def unset_env_var(name: str, key: str, store: EnvironmentStore | None = None) -> None:
    store = store or EnvironmentStore()
    env = store.load(name)
    if key not in env.env:
        raise AisboxError(f"Environment variable is not set: {key}")
    del env.env[key]
    store.save(env)
```

- [ ] **Step 4: Add CLI subcommands**

Modify imports in `src/aisbox/cli.py` to include:

```python
from aisbox.commands import (
    add_mount,
    create_environment,
    delete_environment,
    inspect_environment,
    list_environments,
    remove_mount,
    set_env_var,
    unset_env_var,
)
```

Add an env sub-app after `app = typer.Typer(no_args_is_help=True)`:

```python
env_app = typer.Typer(no_args_is_help=True)
app.add_typer(env_app, name="env")
```

Append commands before `main()`:

```python
@app.command("mount")
def mount(
    name: str = typer.Option(..., "-n", "--name"),
    source: str = typer.Argument(...),
    alias: str = typer.Argument(...),
) -> None:
    try:
        created = add_mount(name, source, alias)
    except AisboxError as exc:
        handle_error(exc)
    typer.echo(f"Mounted {created.alias}")


@app.command("unmount")
def unmount(
    name: str = typer.Option(..., "-n", "--name"),
    alias: str = typer.Argument(...),
) -> None:
    try:
        remove_mount(name, alias)
    except AisboxError as exc:
        handle_error(exc)
    typer.echo(f"Unmounted {alias}")


@env_app.command("set")
def env_set(
    assignment: str = typer.Argument(...),
    name: str = typer.Option(..., "-n", "--name"),
) -> None:
    try:
        key = set_env_var(name, assignment)
    except AisboxError as exc:
        handle_error(exc)
    typer.echo(f"Set {key}")


@env_app.command("unset")
def env_unset(
    key: str = typer.Argument(...),
    name: str = typer.Option(..., "-n", "--name"),
) -> None:
    try:
        unset_env_var(name, key)
    except AisboxError as exc:
        handle_error(exc)
    typer.echo(f"Unset {key}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
pytest tests/test_cli_mutation.py tests/test_cli_core.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/aisbox/commands.py src/aisbox/cli.py tests/test_cli_mutation.py
git commit -m "feat: mutate environment mounts and variables"
```

---

### Task 7: Runtime Docker Commands

**Files:**
- Modify: `src/aisbox/docker.py`
- Modify: `src/aisbox/commands.py`
- Modify: `src/aisbox/cli.py`
- Create: `tests/test_cli_runtime.py`

- [ ] **Step 1: Write failing runtime tests**

Create `tests/test_cli_runtime.py`:

```python
from unittest.mock import Mock

from typer.testing import CliRunner

from aisbox.cli import app


runner = CliRunner()


def setup_env(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    monkeypatch.setattr("aisbox.commands.build_image", lambda agent: None)
    result = runner.invoke(app, ["create", "-n", "demo1", "-a", "claude", "-e", "TOKEN=abc"])
    assert result.exit_code == 0


def test_run_builds_non_interactive_docker_command(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    runner_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", runner_mock)

    result = runner.invoke(app, ["run", "-n", "demo1", "--", "hello"])

    assert result.exit_code == 0
    env, agent, config_source, mode, prompt = runner_mock.call_args.args
    assert env.name == "demo1"
    assert agent.name == "claude"
    assert config_source.endswith("/config/claude")
    assert mode == "run"
    assert prompt == "hello"


def test_attach_and_shell_use_interactive_modes(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    runner_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", runner_mock)

    attach = runner.invoke(app, ["attach", "-n", "demo1"])
    shell = runner.invoke(app, ["shell", "-n", "demo1"])

    assert attach.exit_code == 0
    assert shell.exit_code == 0
    assert runner_mock.call_args_list[0].args[3] == "attach"
    assert runner_mock.call_args_list[1].args[3] == "shell"


def test_rebuild_invokes_image_build_for_stored_agent(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    build_mock = Mock()
    monkeypatch.setattr("aisbox.commands.build_image", build_mock)

    result = runner.invoke(app, ["rebuild", "-n", "demo1"])

    assert result.exit_code == 0
    assert "Rebuilt demo1" in result.stdout
    assert build_mock.call_args.args[0].name == "claude"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_cli_runtime.py -v
```

Expected: FAIL because runtime commands do not exist.

- [ ] **Step 3: Add Docker run command construction**

Append to `src/aisbox/docker.py`:

```python
from aisbox.models import Environment


def container_command(
    env: Environment,
    agent: AgentDefinition,
    config_source: str,
    mode: str,
    prompt: str | None = None,
) -> list[str]:
    command = ["docker", "run", "--rm", "-w", "/workspace"]
    if mode in {"attach", "shell"}:
        command.extend(["-it"])
    command.extend(["-v", f"{env.workspace}:/workspace"])
    command.extend(["-v", f"{config_source}:{agent.config_path}"])
    for mount in env.mounts:
        command.extend(["-v", f"{mount.source}:/workspace/{mount.alias}"])
    for key, value in sorted(env.env.items()):
        command.extend(["-e", f"{key}={value}"])
    command.append(agent.image)
    if mode == "run":
        command.extend(agent.run_command)
        if prompt is not None:
            command.append(prompt)
    elif mode == "attach":
        command.extend(agent.attach_command)
    elif mode == "shell":
        command.extend(agent.shell_command)
    else:
        raise ValueError(f"Unknown container mode: {mode}")
    return command


def run_container(
    env: Environment,
    agent: AgentDefinition,
    config_source: str,
    mode: str,
    prompt: str | None = None,
    runner: Runner = default_runner,
) -> None:
    runner(container_command(env, agent, config_source, mode, prompt), check=True)
```

- [ ] **Step 4: Add runtime command orchestration**

Append to `src/aisbox/commands.py`:

```python
from aisbox.docker import run_container


def run_environment(
    name: str,
    mode: str,
    prompt: str | None = None,
    store: EnvironmentStore | None = None,
) -> None:
    store = store or EnvironmentStore()
    env = store.load(name)
    agent = get_agent(env.agent)
    config_source = str(store.config_dir(env.name, agent.name))
    run_container(env, agent, config_source, mode, prompt)


def rebuild_environment(name: str, store: EnvironmentStore | None = None) -> None:
    store = store or EnvironmentStore()
    env = store.load(name)
    agent = get_agent(env.agent)
    build_image(agent)
    env.image = agent.image
    store.save(env)
```

- [ ] **Step 5: Add runtime CLI commands**

Modify imports in `src/aisbox/cli.py` to include:

```python
    rebuild_environment,
    run_environment,
```

Append commands before `main()`:

```python
@app.command("run", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def run(
    ctx: typer.Context,
    name: str = typer.Option(..., "-n", "--name"),
) -> None:
    prompt = " ".join(ctx.args)
    try:
        run_environment(name, "run", prompt)
    except AisboxError as exc:
        handle_error(exc)


@app.command("attach")
def attach(name: str = typer.Option(..., "-n", "--name")) -> None:
    try:
        run_environment(name, "attach")
    except AisboxError as exc:
        handle_error(exc)


@app.command("shell")
def shell(name: str = typer.Option(..., "-n", "--name")) -> None:
    try:
        run_environment(name, "shell")
    except AisboxError as exc:
        handle_error(exc)


@app.command("rebuild")
def rebuild(name: str = typer.Option(..., "-n", "--name")) -> None:
    try:
        rebuild_environment(name)
    except AisboxError as exc:
        handle_error(exc)
    typer.echo(f"Rebuilt {name}")
```

- [ ] **Step 6: Add focused Docker command tests**

Append to `tests/test_docker.py`:

```python
from aisbox.agents import get_agent
from aisbox.docker import container_command
from aisbox.models import Environment, Mount


def test_container_command_includes_mounts_env_and_prompt():
    env = Environment(
        name="demo1",
        agent="claude",
        env={"TOKEN": "abc"},
        workspace="/tmp/workspace",
        mounts=[Mount(source="/tmp/src", alias="src")],
        image="aisbox/claude:latest",
        created_at="2026-06-05T00:00:00Z",
    )

    command = container_command(env, get_agent("claude"), "/tmp/config/claude", "run", "hello")

    assert command[:4] == ["docker", "run", "--rm", "-w"]
    assert "-v" in command
    assert "/tmp/workspace:/workspace" in command
    assert "/tmp/config/claude:/home/aisbox/.claude" in command
    assert "/tmp/src:/workspace/src" in command
    assert "TOKEN=abc" in command
    assert command[-2:] == ["-p", "hello"]
```

- [ ] **Step 7: Run tests to verify they pass**

Run:

```bash
pytest tests/test_cli_runtime.py tests/test_docker.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/aisbox/docker.py src/aisbox/commands.py src/aisbox/cli.py tests/test_cli_runtime.py tests/test_docker.py
git commit -m "feat: run agent containers"
```

---

### Task 8: Doctor Diagnostics

**Files:**
- Modify: `src/aisbox/commands.py`
- Modify: `src/aisbox/cli.py`
- Create: `tests/test_doctor.py`

- [ ] **Step 1: Write failing doctor tests**

Create `tests/test_doctor.py`:

```python
from typer.testing import CliRunner

from aisbox.cli import app


runner = CliRunner()


def test_doctor_success(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    monkeypatch.setattr("aisbox.commands.docker_available", lambda: True)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "Docker: ok" in result.stdout
    assert "State directory: ok" in result.stdout


def test_doctor_fails_when_docker_unavailable_or_not_permitted(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    monkeypatch.setattr("aisbox.commands.docker_available", lambda: False)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "Docker: missing, unreachable, or permission denied" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_doctor.py -v
```

Expected: FAIL because doctor is not implemented.

- [ ] **Step 3: Implement doctor command data**

Append to `src/aisbox/commands.py`:

```python
from dataclasses import dataclass

from aisbox.agents import supported_agents
from aisbox.docker import docker_available


@dataclass(frozen=True)
class DoctorResult:
    ok: bool
    lines: list[str]


def doctor(store: EnvironmentStore | None = None) -> DoctorResult:
    store = store or EnvironmentStore()
    lines = []
    ok = True
    if docker_available():
        lines.append("Docker: ok")
    else:
        lines.append("Docker: missing, unreachable, or permission denied")
        ok = False
    try:
        store.root.mkdir(parents=True, exist_ok=True)
        probe = store.root / ".doctor-write-test"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink()
        lines.append("State directory: ok")
    except OSError:
        lines.append("State directory: not writable")
        ok = False
    lines.append("Supported agents: " + ", ".join(supported_agents()))
    return DoctorResult(ok=ok, lines=lines)
```

- [ ] **Step 4: Add doctor CLI command**

Modify imports in `src/aisbox/cli.py` to include:

```python
    doctor as run_doctor,
```

Append before `main()`:

```python
@app.command("doctor")
def doctor() -> None:
    result = run_doctor()
    for line in result.lines:
        typer.echo(line)
    if not result.ok:
        raise typer.Exit(code=1)
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
pytest tests/test_doctor.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/aisbox/commands.py src/aisbox/cli.py tests/test_doctor.py
git commit -m "feat: add doctor diagnostics"
```

---

### Task 9: Documentation And Full Verification

**Files:**
- Modify: `README.md`
- Modify: `tests/test_cli_core.py`

- [ ] **Step 1: Add a failing README coverage test**

Append to `tests/test_cli_core.py`:

```python
from pathlib import Path


def test_readme_documents_primary_commands():
    readme = Path("README.md").read_text(encoding="utf-8")

    for command in [
        "aisbox create",
        "aisbox run",
        "aisbox attach",
        "aisbox shell",
        "aisbox mount",
        "aisbox env set",
        "aisbox doctor",
    ]:
        assert command in readme
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_cli_core.py::test_readme_documents_primary_commands -v
```

Expected: FAIL because README usage docs are incomplete.

- [ ] **Step 3: Expand README**

Replace `README.md` with:

```markdown
# aisbox

`aisbox` runs AI coding agents inside isolated Docker environments.

Each environment stores its own config and files under `~/.aisbox/<name>`.
Host `~/.claude` and `~/.codex` directories are not copied or mounted.
Docker must be usable by the current user. `aisbox` does not run Docker through `sudo`.

## Install From This Repository

```bash
pipx install .
```

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Commands

```bash
aisbox create -n demo1 -a claude -e ANTHROPIC_API_KEY=value
aisbox create -n demo1 -a codex --workspace /path/to/source
aisbox run -n demo1 -- "summarize this repository"
aisbox attach -n demo1
aisbox shell -n demo1
aisbox list
aisbox inspect -n demo1
aisbox rebuild -n demo1
aisbox mount -n demo1 /path/to/dir dir
aisbox unmount -n demo1 dir
aisbox env set -n demo1 KEY=VALUE
aisbox env unset -n demo1 KEY
aisbox doctor
aisbox delete -n demo1 --force
```

## Authentication

Authenticate interactively inside the container with `aisbox attach -n demo1`,
or provide explicit API tokens with `-e KEY=VALUE` during create and
`aisbox env set` after creation.
```

- [ ] **Step 4: Run full tests**

Run:

```bash
pytest -v
```

Expected: PASS.

- [ ] **Step 5: Run package import check**

Run:

```bash
python -m pip install -e ".[dev]"
python -c "import aisbox; print(aisbox.__version__)"
```

Expected: prints `0.1.0`.

- [ ] **Step 6: Run CLI help check**

Run:

```bash
python -m aisbox.cli --help
```

Expected: shows Typer help with the `create`, `run`, `attach`, `shell`, `delete`, `list`, `inspect`, `rebuild`, `mount`, `unmount`, `env`, and `doctor` commands.

- [ ] **Step 7: Commit**

```bash
git add README.md tests/test_cli_core.py
git commit -m "docs: document aisbox usage"
```

---

## Plan Self-Review

- Spec coverage: command surface, state layout, isolated config behavior, managed images, fresh containers, validation, packaging, and tests are covered by Tasks 1 through 9.
- Completeness scan: no incomplete sections remain in this plan.
- Type consistency: `Environment`, `Mount`, `AgentDefinition`, `EnvironmentStore`, and command function names are introduced before use in later tasks.
