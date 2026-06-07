# Retained Agent Sessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one retained interactive agent session per environment while renaming the existing disposable interactive command from `attach` to `start`.

**Architecture:** Keep Docker command construction and inspection in `src/aisbox/docker.py`, expose typed container/session records through `src/aisbox/models.py`, orchestrate ownership checks and lifecycle decisions in `src/aisbox/commands.py`, and keep Typer output in `src/aisbox/cli.py`. Docker remains authoritative: retained containers use deterministic names and labels, and no container IDs are persisted in aisbox state.

**Tech Stack:** Python 3.11, Typer, Docker CLI subprocess calls, dataclasses, pytest, `unittest.mock`

---

## File Structure

- Modify `src/aisbox/models.py`: add typed Docker container and retained-session records.
- Modify `src/aisbox/docker.py`: rename interactive mode to `start`, build retained container commands, inspect/list/attach/remove Docker containers, and parse Docker JSON.
- Modify `src/aisbox/commands.py`: orchestrate disposable starts, retained creation/attachment/replacement, listing, killing, and deletion protection.
- Modify `src/aisbox/cli.py`: expose `start`, new retained `attach`, `sessions`, and `kill` commands with detach guidance.
- Modify `tests/test_docker.py`: verify Docker command construction, parsing, lookup, listing, attachment, and removal.
- Modify `tests/test_cli_runtime.py`: verify command-level and CLI-level retained session behavior with Docker mocked.
- Modify `tests/test_cli_core.py`: verify command documentation and clean user-facing failures.
- Modify `tests/test_repository_docs.py`: update repository documentation assertions for disposable and retained workflows.
- Modify `README.md`: document the breaking rename and retained-session lifecycle.

### Task 1: Add Typed Docker Session Records

**Files:**
- Modify: `src/aisbox/models.py`
- Test: `tests/test_docker.py`

- [ ] **Step 1: Write the failing model construction test**

Add this test to `tests/test_docker.py`:

```python
from aisbox.models import DockerContainer, RetainedSession


def test_docker_and_retained_session_records_expose_lifecycle_fields():
    container = DockerContainer(
        name="aisbox-demo1",
        status="running",
        labels={
            "dev.aisbox.managed": "true",
            "dev.aisbox.environment": "demo1",
            "dev.aisbox.agent": "claude",
        },
    )
    session = RetainedSession(
        environment="demo1",
        agent="claude",
        container="aisbox-demo1",
        status="running",
    )

    assert container.name == session.container
    assert container.labels["dev.aisbox.environment"] == session.environment
    assert session.status == "running"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
.venv/bin/pytest tests/test_docker.py::test_docker_and_retained_session_records_expose_lifecycle_fields -v
```

Expected: FAIL because `DockerContainer` and `RetainedSession` do not exist.

- [ ] **Step 3: Add the model records**

Append to `src/aisbox/models.py`:

```python
@dataclass(frozen=True)
class DockerContainer:
    name: str
    status: str
    labels: dict[str, str]


@dataclass(frozen=True)
class RetainedSession:
    environment: str
    agent: str
    container: str
    status: str
```

- [ ] **Step 4: Run the focused test**

Run:

```bash
.venv/bin/pytest tests/test_docker.py::test_docker_and_retained_session_records_expose_lifecycle_fields -v
```

Expected: PASS.

- [ ] **Step 5: Commit the model change**

```bash
git add src/aisbox/models.py tests/test_docker.py
git commit -m "feat: add retained session models"
```

### Task 2: Rename Disposable Interactive Mode and Build Retained Containers

**Files:**
- Modify: `src/aisbox/docker.py:49-87`
- Modify: `tests/test_docker.py:64-138`

- [ ] **Step 1: Replace the old attach-mode tests with start and retained-command tests**

In `tests/test_docker.py`, rename the existing interactive test and add retained assertions:

```python
def make_environment() -> Environment:
    return Environment(
        name="demo1",
        agent="claude",
        env={"TOKEN": "abc"},
        workspace="/tmp/workspace",
        mounts=[Mount(source="/tmp/src", alias="src")],
        image="aisbox/claude:latest",
        created_at="2026-06-05T00:00:00Z",
    )


def test_container_command_start_mode_is_disposable_and_interactive():
    agent = get_agent("claude")

    command = container_command(
        make_environment(),
        agent,
        "/tmp/config",
        "start",
    )

    assert command[:4] == ["docker", "run", "--rm", "-w"]
    assert "-it" in command
    assert command[-len(agent.attach_command) :] == agent.attach_command


def test_container_command_retained_start_has_name_labels_and_no_rm():
    agent = get_agent("claude")

    command = container_command(
        make_environment(),
        agent,
        "/tmp/config",
        "start",
        retained=True,
    )

    assert "--rm" not in command
    assert ["--name", "aisbox-demo1"] == command[
        command.index("--name") : command.index("--name") + 2
    ]
    for label in [
        "dev.aisbox.managed=true",
        "dev.aisbox.environment=demo1",
        "dev.aisbox.agent=claude",
    ]:
        assert label in command
    assert "-it" in command
    assert "/tmp/workspace:/workspace" in command
    assert "/tmp/config:/home/aisbox" in command
    assert "/tmp/src:/workspace/src" in command
    assert "TOKEN=abc" in command
    assert command[-len(agent.attach_command) :] == agent.attach_command
```

Update other tests to use `make_environment()` where doing so removes duplicate setup. Keep explicit environments in tests that require a different image.

- [ ] **Step 2: Run the focused command tests to verify they fail**

Run:

```bash
.venv/bin/pytest tests/test_docker.py -k "container_command" -v
```

Expected: FAIL because `start` and the `retained` argument are not supported.

- [ ] **Step 3: Implement deterministic naming and retained command construction**

In `src/aisbox/docker.py`, add constants and replace `container_command`:

```python
MANAGED_LABEL = "dev.aisbox.managed"
ENVIRONMENT_LABEL = "dev.aisbox.environment"
AGENT_LABEL = "dev.aisbox.agent"


def retained_container_name(environment_name: str) -> str:
    return f"aisbox-{environment_name}"


def container_command(
    env: Environment,
    agent: AgentDefinition,
    config_source: str,
    mode: str,
    prompt: str | None = None,
    retained: bool = False,
) -> list[str]:
    command = ["docker", "run"]
    if retained:
        command.extend(
            [
                "--name",
                retained_container_name(env.name),
                "--label",
                f"{MANAGED_LABEL}=true",
                "--label",
                f"{ENVIRONMENT_LABEL}={env.name}",
                "--label",
                f"{AGENT_LABEL}={agent.name}",
            ]
        )
    else:
        command.append("--rm")
    command.extend(["-w", "/workspace"])
    if mode in {"start", "shell"}:
        command.append("-it")
    command.extend(["-v", f"{env.workspace}:/workspace"])
    command.extend(["-v", f"{config_source}:{agent.config_path}"])
    for mount in env.mounts:
        command.extend(["-v", f"{mount.source}:/workspace/{mount.alias}"])
    for key, value in sorted(env.env.items()):
        command.extend(["-e", f"{key}={value}"])
    command.append(env.image)
    if mode == "run":
        command.extend(agent.run_command)
        if prompt is not None:
            command.append(prompt)
    elif mode == "start":
        command.extend(agent.attach_command)
    elif mode == "shell":
        command.extend(agent.shell_command)
    else:
        raise ValueError(f"Unknown container mode: {mode}")
    return command
```

Change `run_container` so it forwards the retained flag:

```python
def run_container(
    env: Environment,
    agent: AgentDefinition,
    config_source: str,
    mode: str,
    prompt: str | None = None,
    retained: bool = False,
    runner: Runner = default_runner,
) -> None:
    runner(
        container_command(
            env,
            agent,
            config_source,
            mode,
            prompt,
            retained=retained,
        ),
        check=True,
    )
```

- [ ] **Step 4: Run all Docker command tests**

Run:

```bash
.venv/bin/pytest tests/test_docker.py -k "container_command" -v
```

Expected: PASS, including disposable `run`, `start`, and `shell` behavior.

- [ ] **Step 5: Commit retained command construction**

```bash
git add src/aisbox/docker.py tests/test_docker.py
git commit -m "feat: build retained agent containers"
```

### Task 3: Add Docker Inspection and Lifecycle Primitives

**Files:**
- Modify: `src/aisbox/docker.py`
- Modify: `tests/test_docker.py`

- [ ] **Step 1: Write failing tests for inspection, listing, attachment, and removal**

Add imports and tests in `tests/test_docker.py`:

```python
import json

from aisbox.docker import (
    attach_container,
    inspect_container,
    list_retained_containers,
    remove_container,
)


def completed(
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["docker"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_inspect_container_parses_name_state_and_labels():
    payload = {
        "Name": "/aisbox-demo1",
        "State": {"Status": "running"},
        "Config": {
            "Labels": {
                "dev.aisbox.managed": "true",
                "dev.aisbox.environment": "demo1",
                "dev.aisbox.agent": "claude",
            }
        },
    }
    runner = Mock(return_value=completed(stdout=json.dumps(payload)))

    container = inspect_container("aisbox-demo1", runner=runner)

    assert container is not None
    assert container.name == "aisbox-demo1"
    assert container.status == "running"
    assert container.labels["dev.aisbox.environment"] == "demo1"


def test_inspect_container_returns_none_only_for_missing_container():
    runner = Mock(
        return_value=completed(
            returncode=1,
            stderr="Error: No such container: aisbox-demo1",
        )
    )

    assert inspect_container("aisbox-demo1", runner=runner) is None


def test_inspect_container_raises_for_other_docker_failures():
    runner = Mock(return_value=completed(returncode=1, stderr="permission denied"))

    with pytest.raises(subprocess.CalledProcessError):
        inspect_container("aisbox-demo1", runner=runner)


def test_list_retained_containers_parses_json_lines():
    records = [
        {
            "Names": "aisbox-demo1",
            "State": "running",
            "Labels": (
                "dev.aisbox.managed=true,"
                "dev.aisbox.environment=demo1,"
                "dev.aisbox.agent=claude"
            ),
        },
        {
            "Names": "aisbox-demo2",
            "State": "exited",
            "Labels": (
                "dev.aisbox.managed=true,"
                "dev.aisbox.environment=demo2,"
                "dev.aisbox.agent=codex"
            ),
        },
    ]
    runner = Mock(
        return_value=completed(
            stdout="\n".join(json.dumps(record) for record in records)
        )
    )

    containers = list_retained_containers(runner=runner)

    assert [container.name for container in containers] == [
        "aisbox-demo1",
        "aisbox-demo2",
    ]
    assert containers[1].status == "exited"


def test_attach_and_remove_container_invoke_exact_docker_commands():
    runner = Mock()

    attach_container("aisbox-demo1", runner=runner)
    remove_container("aisbox-demo1", runner=runner)

    assert runner.call_args_list[0].args[0] == [
        "docker",
        "attach",
        "aisbox-demo1",
    ]
    assert runner.call_args_list[1].args[0] == [
        "docker",
        "rm",
        "--force",
        "aisbox-demo1",
    ]
```

Also add `import pytest` at the top of `tests/test_docker.py`.

- [ ] **Step 2: Run the new lifecycle tests to verify they fail**

Run:

```bash
.venv/bin/pytest tests/test_docker.py -k "inspect_container or list_retained or attach_and_remove" -v
```

Expected: FAIL because the Docker lifecycle functions do not exist.

- [ ] **Step 3: Implement Docker JSON parsing and lifecycle calls**

Add `import json`, import `DockerContainer`, and add these functions to
`src/aisbox/docker.py`:

```python
def _parse_labels(value: str | None) -> dict[str, str]:
    labels: dict[str, str] = {}
    if not value:
        return labels
    for item in value.split(","):
        key, separator, label_value = item.partition("=")
        if separator:
            labels[key] = label_value
    return labels


def inspect_container(
    name: str,
    runner: Runner = default_runner,
) -> DockerContainer | None:
    command = [
        "docker",
        "container",
        "inspect",
        "--format",
        "{{json .}}",
        name,
    ]
    result = runner(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        if "No such container" in result.stderr or "No such object" in result.stderr:
            return None
        raise subprocess.CalledProcessError(
            result.returncode,
            command,
            output=result.stdout,
            stderr=result.stderr,
        )
    payload = json.loads(result.stdout)
    return DockerContainer(
        name=str(payload["Name"]).removeprefix("/"),
        status=str(payload["State"]["Status"]),
        labels={
            str(key): str(value)
            for key, value in (payload["Config"].get("Labels") or {}).items()
        },
    )


def list_retained_containers(
    runner: Runner = default_runner,
) -> list[DockerContainer]:
    command = [
        "docker",
        "ps",
        "--all",
        "--filter",
        f"label={MANAGED_LABEL}=true",
        "--format",
        "{{json .}}",
    ]
    result = runner(command, check=True, capture_output=True, text=True)
    containers = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        containers.append(
            DockerContainer(
                name=str(payload["Names"]),
                status=str(payload["State"]),
                labels=_parse_labels(payload.get("Labels")),
            )
        )
    return containers


def attach_container(name: str, runner: Runner = default_runner) -> None:
    runner(["docker", "attach", name], check=True)


def remove_container(name: str, runner: Runner = default_runner) -> None:
    runner(["docker", "rm", "--force", name], check=True)
```

Do not catch `json.JSONDecodeError` here. Malformed Docker output is an
unexpected integration failure and should be translated at the command
boundary in the next task.

- [ ] **Step 4: Run the full Docker unit test file**

Run:

```bash
.venv/bin/pytest tests/test_docker.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Docker lifecycle primitives**

```bash
git add src/aisbox/docker.py tests/test_docker.py
git commit -m "feat: manage retained docker containers"
```

### Task 4: Orchestrate Retained Session Ownership and Lifecycle

**Files:**
- Modify: `src/aisbox/commands.py:9-183`
- Modify: `tests/test_cli_runtime.py`
- Modify: `tests/test_cli_core.py`

- [ ] **Step 1: Write failing command-layer lifecycle tests**

Add imports and tests to `tests/test_cli_runtime.py`:

```python
import subprocess

import pytest

from aisbox.commands import (
    attach_environment,
    delete_environment,
    kill_session,
    list_sessions,
    start_environment,
)
from aisbox.errors import AisboxError
from aisbox.models import DockerContainer


def managed_container(
    *,
    environment: str = "demo1",
    agent: str = "claude",
    status: str = "running",
) -> DockerContainer:
    return DockerContainer(
        name=f"aisbox-{environment}",
        status=status,
        labels={
            "dev.aisbox.managed": "true",
            "dev.aisbox.environment": environment,
            "dev.aisbox.agent": agent,
        },
    )


def test_start_environment_without_keep_runs_disposable_start(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    run_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", run_mock)

    start_environment("demo1", keep=False)

    assert run_mock.call_args.args[3] == "start"
    assert run_mock.call_args.kwargs == {}


def test_retained_start_creates_missing_session(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr("aisbox.commands.inspect_container", lambda name: None)
    run_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", run_mock)

    start_environment("demo1", keep=True)

    assert run_mock.call_args.args[3] == "start"
    assert run_mock.call_args.kwargs == {"retained": True}


def test_attach_joins_running_retained_session(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "aisbox.commands.inspect_container",
        lambda name: managed_container(),
    )
    attach_mock = Mock()
    monkeypatch.setattr("aisbox.commands.attach_container", attach_mock)

    attach_environment("demo1")

    attach_mock.assert_called_once_with("aisbox-demo1")


def test_attach_replaces_stopped_retained_session(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "aisbox.commands.inspect_container",
        lambda name: managed_container(status="exited"),
    )
    remove_mock = Mock()
    run_mock = Mock()
    monkeypatch.setattr("aisbox.commands.remove_container", remove_mock)
    monkeypatch.setattr("aisbox.commands.run_container", run_mock)

    attach_environment("demo1")

    remove_mock.assert_called_once_with("aisbox-demo1")
    assert run_mock.call_args.kwargs == {"retained": True}


def test_attach_rejects_unmanaged_name_collision(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "aisbox.commands.inspect_container",
        lambda name: DockerContainer(name=name, status="running", labels={}),
    )

    with pytest.raises(AisboxError, match="not managed by aisbox"):
        attach_environment("demo1")


def test_list_sessions_returns_only_running_valid_environments(
    tmp_path, monkeypatch
):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "aisbox.commands.list_retained_containers",
        lambda: [
            managed_container(),
            managed_container(environment="demo1", status="exited"),
            managed_container(environment="missing", agent="codex"),
        ],
    )

    sessions = list_sessions()

    assert [(item.environment, item.agent, item.status) for item in sessions] == [
        ("demo1", "claude", "running")
    ]


def test_kill_removes_owned_running_or_stopped_container(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "aisbox.commands.inspect_container",
        lambda name: managed_container(status="exited"),
    )
    remove_mock = Mock()
    monkeypatch.setattr("aisbox.commands.remove_container", remove_mock)

    kill_session("demo1")

    remove_mock.assert_called_once_with("aisbox-demo1")


def test_kill_errors_when_retained_container_is_missing(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr("aisbox.commands.inspect_container", lambda name: None)

    with pytest.raises(AisboxError, match="No retained session"):
        kill_session("demo1")


def test_attach_translates_docker_inspection_failure(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "aisbox.commands.inspect_container",
        lambda name: (_ for _ in ()).throw(
            subprocess.CalledProcessError(
                returncode=1,
                cmd=["docker", "container", "inspect", name],
            )
        ),
    )

    with pytest.raises(AisboxError, match="Docker retained session operation failed"):
        attach_environment("demo1")


def test_delete_refuses_when_owned_retained_container_exists(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "aisbox.commands.inspect_container",
        lambda name: managed_container(),
    )

    with pytest.raises(AisboxError, match=r"aisbox kill -n demo1"):
        delete_environment("demo1")
```

- [ ] **Step 2: Isolate existing deletion tests from real Docker**

In each existing `tests/test_cli_core.py` test that invokes `aisbox delete`,
add this before the CLI invocation:

```python
monkeypatch.setattr("aisbox.commands.inspect_container", lambda name: None)
```

This applies to the force-delete and default-environment deletion tests. It
keeps those tests focused on state deletion while the new retained-container
tests cover Docker-aware protection.

- [ ] **Step 3: Run the command-layer tests to verify they fail**

Run:

```bash
.venv/bin/pytest tests/test_cli_runtime.py -k "start_environment or retained or attach_ or list_sessions or kill_ or delete_refuses" -v
```

Expected: FAIL because retained-session command functions do not exist.

- [ ] **Step 4: Implement ownership validation and shared Docker error translation**

Expand the imports from `aisbox.docker` in `src/aisbox/commands.py`:

```python
from aisbox.docker import (
    AGENT_LABEL,
    ENVIRONMENT_LABEL,
    MANAGED_LABEL,
    attach_container,
    build_image,
    docker_available,
    inspect_container,
    list_retained_containers,
    remove_container,
    retained_container_name,
    run_container,
)
```

Import `json`, `DockerContainer`, and `RetainedSession`, then add:

```python
def _docker_failure(action: str, environment: str | None = None) -> AisboxError:
    suffix = f" for environment: {environment}" if environment else ""
    return AisboxError(f"Docker {action} failed{suffix}")


def _owned_retained_container(
    env: Environment,
    container: DockerContainer | None,
) -> DockerContainer | None:
    if container is None:
        return None
    expected = {
        MANAGED_LABEL: "true",
        ENVIRONMENT_LABEL: env.name,
        AGENT_LABEL: env.agent,
    }
    if (
        container.name != retained_container_name(env.name)
        or any(container.labels.get(key) != value for key, value in expected.items())
    ):
        raise AisboxError(
            f"Container name {container.name} is not managed by aisbox "
            f"for environment: {env.name}"
        )
    return container


def _inspect_retained(env: Environment) -> DockerContainer | None:
    return _owned_retained_container(
        env,
        inspect_container(retained_container_name(env.name)),
    )
```

The following implementation steps include the exact exception translation for
each public lifecycle function. Preserve `AisboxError` ownership and
missing-session failures; translate `FileNotFoundError`, Docker subprocess
failures, and malformed Docker JSON at the command boundary.

- [ ] **Step 5: Implement disposable start and retained ensure/attach**

Keep `run_environment` for `run` and `shell`, but allow the renamed `start`
mode. Add:

```python
def _run_retained(env: Environment, store: EnvironmentStore) -> None:
    agent = get_agent(env.agent)
    run_container(
        env,
        agent,
        str(store.config_dir(env.name)),
        "start",
        retained=True,
    )


def _ensure_retained_session(
    name: str,
    store: EnvironmentStore | None = None,
) -> None:
    store = store or EnvironmentStore()
    env = store.load(name)
    try:
        container = _inspect_retained(env)
        if container is None:
            _run_retained(env, store)
        elif container.status == "running":
            attach_container(container.name)
        else:
            remove_container(container.name)
            _run_retained(env, store)
    except FileNotFoundError as exc:
        raise AisboxError("Docker is not installed or not available on PATH") from exc
    except (
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as exc:
        raise _docker_failure("retained session operation", env.name) from exc


def start_environment(
    name: str,
    keep: bool,
    store: EnvironmentStore | None = None,
) -> None:
    if keep:
        _ensure_retained_session(name, store)
        return
    run_environment(name, "start", store=store)


def attach_environment(
    name: str,
    store: EnvironmentStore | None = None,
) -> None:
    _ensure_retained_session(name, store)
```

This intentionally gives `start --keep` and `attach` exactly the same retained
resolution path.

- [ ] **Step 6: Implement listing, killing, and deletion protection**

Add:

```python
def list_sessions(
    store: EnvironmentStore | None = None,
) -> list[RetainedSession]:
    store = store or EnvironmentStore()
    try:
        sessions = []
        for container in list_retained_containers():
            if container.status != "running":
                continue
            environment_name = container.labels.get(ENVIRONMENT_LABEL)
            agent_name = container.labels.get(AGENT_LABEL)
            if (
                container.labels.get(MANAGED_LABEL) != "true"
                or environment_name is None
                or agent_name is None
                or not store.exists(environment_name)
            ):
                continue
            env = store.load(environment_name)
            if (
                env.agent != agent_name
                or container.name != retained_container_name(env.name)
            ):
                continue
            sessions.append(
                RetainedSession(
                    environment=env.name,
                    agent=env.agent,
                    container=container.name,
                    status=container.status,
                )
            )
        return sorted(sessions, key=lambda session: session.environment)
    except FileNotFoundError as exc:
        raise AisboxError("Docker is not installed or not available on PATH") from exc
    except (
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as exc:
        raise _docker_failure("session listing") from exc


def kill_session(
    name: str,
    store: EnvironmentStore | None = None,
) -> None:
    store = store or EnvironmentStore()
    env = store.load(name)
    try:
        container = _inspect_retained(env)
        if container is None:
            raise AisboxError(f"No retained session exists for environment: {name}")
        remove_container(container.name)
    except AisboxError:
        raise
    except FileNotFoundError as exc:
        raise AisboxError("Docker is not installed or not available on PATH") from exc
    except (
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as exc:
        raise _docker_failure("container removal", env.name) from exc
```

Replace `delete_environment` with:

```python
def delete_environment(name: str, store: EnvironmentStore | None = None) -> None:
    store = store or EnvironmentStore()
    env = store.load(name)
    try:
        container = _inspect_retained(env)
    except FileNotFoundError as exc:
        raise AisboxError("Docker is not installed or not available on PATH") from exc
    except (
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as exc:
        raise _docker_failure("container inspection", env.name) from exc
    if container is not None:
        raise AisboxError(
            f"Environment {name} has a retained session; "
            f"run 'aisbox kill -n {name}' first"
        )
    store.delete(name)
```

- [ ] **Step 7: Run the command-layer tests**

Run:

```bash
.venv/bin/pytest tests/test_cli_runtime.py -k "start_environment or retained or attach_ or list_sessions or kill_ or delete_refuses" -v
```

Expected: PASS.

- [ ] **Step 8: Run existing command tests for regressions**

Run:

```bash
.venv/bin/pytest tests/test_cli_runtime.py tests/test_cli_core.py -v
```

Expected: existing old-`attach` assertions fail, identifying the CLI rename
work for Task 5; unrelated tests, including deletion, pass.

- [ ] **Step 9: Commit lifecycle orchestration**

```bash
git add src/aisbox/commands.py tests/test_cli_runtime.py tests/test_cli_core.py
git commit -m "feat: orchestrate retained agent sessions"
```

### Task 5: Expose the New CLI Surface

**Files:**
- Modify: `src/aisbox/cli.py:8-270`
- Modify: `tests/test_cli_runtime.py:77-88`
- Modify: `tests/test_cli_core.py:242-270`

- [ ] **Step 1: Write failing CLI tests for start, attach, sessions, and kill**

Replace `test_attach_and_shell_use_interactive_modes` and add:

```python
def test_start_and_shell_use_disposable_interactive_modes(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    start_mock = Mock()
    runner_mock = Mock()
    monkeypatch.setattr("aisbox.cli.start_environment", start_mock)
    monkeypatch.setattr("aisbox.commands.run_container", runner_mock)

    started = runner.invoke(app, ["start", "-n", "demo1"])
    shell = runner.invoke(app, ["shell", "-n", "demo1"])

    assert started.exit_code == 0
    assert shell.exit_code == 0
    start_mock.assert_called_once_with("demo1", False)
    assert runner_mock.call_args.args[3] == "shell"


def test_retained_commands_print_guidance_and_invoke_lifecycle(
    tmp_path, monkeypatch
):
    setup_env(tmp_path, monkeypatch)
    start_mock = Mock()
    attach_mock = Mock()
    monkeypatch.setattr("aisbox.cli.start_environment", start_mock)
    monkeypatch.setattr("aisbox.cli.attach_environment", attach_mock)

    started = runner.invoke(app, ["start", "-n", "demo1", "--keep"])
    attached = runner.invoke(app, ["attach", "-n", "demo1"])

    assert started.exit_code == 0
    assert attached.exit_code == 0
    assert "Ctrl-p Ctrl-q" in started.stdout
    assert "Ctrl-c may stop" in started.stdout
    assert "Ctrl-p Ctrl-q" in attached.stdout
    start_mock.assert_called_once_with("demo1", True)
    attach_mock.assert_called_once_with("demo1")


def test_sessions_lists_rows_and_handles_empty_results(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "aisbox.cli.list_sessions",
        lambda: [
            RetainedSession(
                environment="demo1",
                agent="claude",
                container="aisbox-demo1",
                status="running",
            )
        ],
    )

    listed = runner.invoke(app, ["sessions"])

    assert listed.exit_code == 0
    assert "demo1\tclaude\taisbox-demo1\trunning" in listed.stdout

    monkeypatch.setattr("aisbox.cli.list_sessions", lambda: [])
    empty = runner.invoke(app, ["sessions"])

    assert empty.exit_code == 0
    assert empty.stdout.strip() == "No retained sessions found"


def test_kill_uses_environment_selection_and_reports_success(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    kill_mock = Mock()
    monkeypatch.setattr("aisbox.cli.kill_session", kill_mock)

    result = runner.invoke(app, ["kill", "-n", "demo1"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "Killed retained session for demo1"
    kill_mock.assert_called_once_with("demo1")
```

Import `RetainedSession` into `tests/test_cli_runtime.py`.

In `tests/test_cli_core.py`, update the README command list to include:

```python
"aisbox start",
"aisbox attach",
"aisbox sessions",
"aisbox kill",
```

- [ ] **Step 2: Run the new CLI tests to verify they fail**

Run:

```bash
.venv/bin/pytest tests/test_cli_runtime.py -k "start_and_shell or retained_commands or sessions_ or kill_" -v
```

Expected: FAIL because the CLI still exposes the old `attach` behavior.

- [ ] **Step 3: Add command imports and retained guidance**

Update the `aisbox.commands` imports in `src/aisbox/cli.py` to include:

```python
attach_environment,
kill_session,
list_sessions,
start_environment,
```

Add:

```python
RETAINED_DETACH_GUIDANCE = (
    "Detach without stopping: Ctrl-p Ctrl-q. "
    "Ctrl-c may stop the agent and session."
)
```

- [ ] **Step 4: Replace old attach and add retained commands**

Replace the old `attach` function and add:

```python
@app.command("start", help="Start an interactive agent.")
def start(
    name: str | None = typer.Option(None, "-n", "--name"),
    keep: bool = typer.Option(
        False,
        "--keep",
        help="Keep one retained session for later attachment.",
    ),
) -> None:
    effective_name = effective_environment_name(name)
    if keep:
        typer.echo(RETAINED_DETACH_GUIDANCE)
    try:
        start_environment(effective_name, keep)
    except AisboxError as exc:
        handle_error(exc)


@app.command(
    "attach",
    help="Attach to a retained agent session, starting one when needed.",
)
def attach(name: str | None = typer.Option(None, "-n", "--name")) -> None:
    effective_name = effective_environment_name(name)
    typer.echo(RETAINED_DETACH_GUIDANCE)
    try:
        attach_environment(effective_name)
    except AisboxError as exc:
        handle_error(exc)


@app.command("sessions", help="List running retained agent sessions.")
def sessions() -> None:
    try:
        retained = list_sessions()
    except AisboxError as exc:
        handle_error(exc)
    if not retained:
        typer.echo("No retained sessions found")
        return
    for session in retained:
        typer.echo(
            f"{session.environment}\t{session.agent}\t"
            f"{session.container}\t{session.status}"
        )


@app.command("kill", help="Stop and remove a retained agent session.")
def kill(name: str | None = typer.Option(None, "-n", "--name")) -> None:
    effective_name = effective_environment_name(name)
    try:
        kill_session(effective_name)
    except AisboxError as exc:
        handle_error(exc)
    typer.echo(f"Killed retained session for {effective_name}")
```

- [ ] **Step 5: Add clean-failure CLI coverage**

Add to `tests/test_cli_runtime.py`:

```python
def test_retained_cli_errors_do_not_emit_tracebacks(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "aisbox.cli.kill_session",
        lambda name: (_ for _ in ()).throw(AisboxError("No retained session")),
    )

    result = runner.invoke(app, ["kill", "-n", "demo1"])

    assert result.exit_code == 1
    assert "Error: No retained session" in result.stderr
    assert "Traceback" not in result.stderr
```

- [ ] **Step 6: Run CLI tests**

Run:

```bash
.venv/bin/pytest tests/test_cli_runtime.py tests/test_cli_core.py -v
```

Expected: PASS except documentation-content assertions that require README
updates in Task 6.

- [ ] **Step 7: Commit the CLI surface**

```bash
git add src/aisbox/cli.py tests/test_cli_runtime.py tests/test_cli_core.py
git commit -m "feat: expose retained session commands"
```

### Task 6: Update User Documentation and Documentation Tests

**Files:**
- Modify: `README.md:1-170`
- Modify: `tests/test_repository_docs.py:436-553`
- Modify: `tests/test_cli_core.py:242-270`

- [ ] **Step 1: Write failing documentation assertions**

Update `tests/test_repository_docs.py` so command coverage includes:

```python
"aisbox start",
"aisbox attach",
"aisbox sessions",
"aisbox kill",
```

Replace the unconditional disposable-container assertion with:

```python
for text in [
    "disposable by default",
    "explicitly retained",
    "docker run --rm",
    "ctrl-p ctrl-q",
    "ctrl-c may stop",
    "aisbox start --keep",
    "aisbox sessions",
    "aisbox kill",
]:
    assert text in normalized
```

In `test_readme_places_delete_after_environment_operations`, require all of
these to appear before delete:

```python
"aisbox start -n demo1",
"aisbox start -n demo1 --keep",
"aisbox attach -n demo1",
"aisbox sessions",
"aisbox kill -n demo1",
```

Update `tests/test_cli_core.py::test_readme_documents_primary_commands` with
the same new command names.

- [ ] **Step 2: Run documentation tests to verify they fail**

Run:

```bash
.venv/bin/pytest tests/test_repository_docs.py tests/test_cli_core.py::test_readme_documents_primary_commands -v
```

Expected: FAIL because README still describes all runtime containers as
disposable and uses old `attach` semantics.

- [ ] **Step 3: Update README safety, authentication, and persistence text**

Make these semantic changes in `README.md`:

```markdown
`aisbox` runs Claude Code and Codex CLI inside Docker containers that are
disposable by default, with explicit persistence for workspaces and agent
configuration and optional retained interactive sessions.
```

Change the safety bullet to:

```markdown
- Runtime containers are disposable by default. Sessions created with
  `start --keep` or `attach` are explicitly retained until `aisbox kill`.
  Persistence comes from explicit bind mounts and stored environment
  configuration.
```

Change authentication to use:

```markdown
Use `aisbox start -n demo1` to authenticate interactively inside a disposable
container, or use an empty assignment to enter an API token at a hidden prompt.
```

Change persistence text to state:

```markdown
Agent configuration persists under `<state-root>/<name>/config`. `run`, plain
`start`, and `shell` use `docker run --rm` and are removed after the container
exits. Retained sessions are opt-in.
```

- [ ] **Step 4: Add a retained sessions section**

Add before `## Commands`:

````markdown
## Retained Sessions

The normal interactive workflow is disposable:

```bash
aisbox start -n demo1
```

To keep one interactive agent session for an environment, start it with:

```bash
aisbox start -n demo1 --keep
```

Detach without stopping the session with Docker's `Ctrl-p Ctrl-q` sequence.
`Ctrl-c` may stop the agent and session. Rejoin the running session, list all
running retained sessions, or stop and remove it with:

```bash
aisbox attach -n demo1
aisbox sessions
aisbox kill -n demo1
```

`attach` starts a retained session when none exists and replaces a stopped
session. A retained container keeps the mounts, environment variables, and
image it started with; kill and recreate it to apply configuration changes.
Each environment supports at most one retained session.
````

- [ ] **Step 5: Update the command reference**

Ensure the README command block contains:

```bash
aisbox run -n demo1 -- "summarize this repository"
aisbox start -n demo1
aisbox start -n demo1 --keep
aisbox attach -n demo1
aisbox sessions
aisbox kill -n demo1
aisbox shell -n demo1
```

Keep `aisbox delete -n demo1 --force` after `kill` because deletion refuses
while a retained container exists.

- [ ] **Step 6: Run documentation tests**

Run:

```bash
.venv/bin/pytest tests/test_repository_docs.py tests/test_cli_core.py::test_readme_documents_primary_commands -v
```

Expected: PASS.

- [ ] **Step 7: Commit documentation**

```bash
git add README.md tests/test_repository_docs.py tests/test_cli_core.py
git commit -m "docs: explain retained agent sessions"
```

### Task 7: Full Regression and CLI Verification

**Files:**
- Modify only if verification exposes a defect in files already covered above.

- [ ] **Step 1: Run formatting and whitespace checks**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 2: Run the full pytest suite**

Run:

```bash
.venv/bin/pytest
```

Expected: all tests pass.

- [ ] **Step 3: Verify the command help surface**

Run:

```bash
.venv/bin/python -m aisbox.cli --help
.venv/bin/python -m aisbox.cli start --help
.venv/bin/python -m aisbox.cli attach --help
.venv/bin/python -m aisbox.cli sessions --help
.venv/bin/python -m aisbox.cli kill --help
```

Expected:

- root help contains `start`, `attach`, `sessions`, and `kill`
- `start --help` documents `--keep`
- `attach` describes retained attachment rather than disposable startup
- commands exit successfully without requiring Docker

- [ ] **Step 4: Verify no old disposable attach implementation remains**

Run:

```bash
rg -n '"attach"|mode == "attach"|run_environment\\([^\\n]*"attach"' src tests README.md
```

Expected: matches refer only to the new retained CLI command, Docker
`attach_container`, documentation, or test names. There is no container mode
named `attach`.

- [ ] **Step 5: Review the final diff against the design**

Run:

```bash
git diff 0e3c3d3 -- src/aisbox tests README.md
```

Confirm:

- one retained session per environment
- Docker name and labels match the spec
- unrelated name collisions are never adopted or removed
- stopped sessions are replaced by `start --keep` and `attach`
- `sessions` lists only running valid sessions
- `kill` removes running or stopped retained containers
- deletion requires killing retained state first
- disposable behavior remains the default

- [ ] **Step 6: Commit any verification fixes**

If verification required changes:

```bash
git add src/aisbox tests README.md
git commit -m "fix: complete retained session lifecycle"
```

If no changes were needed, do not create an empty commit.
