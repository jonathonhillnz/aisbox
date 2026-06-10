# Env-File Security Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent API keys and secrets from appearing in process listings by replacing `-e KEY=VALUE` Docker arguments with `--env-file` backed by a temporary 0600 file.

**Architecture:** Three changes in `src/aisbox/docker.py`: (1) a `_env_file_for` context manager that writes env vars to a temp file and cleans up after, (2) an optional `env_file` parameter on `container_command` that appends `--env-file` instead of `-e`, (3) `run_container` wraps the runner call with the context manager. Tests in `tests/test_docker.py`.

**Tech Stack:** Python 3.12+, `tempfile`, `contextlib.contextmanager`, pytest with `unittest.mock.Mock`

**Spec:** `docs/superpowers/specs/2026-06-10-env-file-security-design.md`

---

### Task 1: `_env_file_for` context manager — test then implement

**Files:**
- Modify: `src/aisbox/docker.py`
- Modify: `tests/test_docker.py`

- [ ] **Step 1: Add import of `_env_file_for` to the test module**

In `tests/test_docker.py`, add `_env_file_for` to the imports from `aisbox.docker`:

```python
from aisbox.docker import (
    ...
    _env_file_for,
    build_image,
    container_command,
    ...
)
```

- [ ] **Step 2: Write tests for `_env_file_for` — creates temp file with correct content and permissions**

Append to `tests/test_docker.py`:

```python
import os
import stat


def test_env_file_for_creates_temp_file_with_key_value_content():
    env = {"ANTHROPIC_API_KEY": "sk-secret-123", "OPENAI_API_KEY": "sk-other-456"}

    with _env_file_for(env) as env_file:
        assert env_file is not None
        content = open(env_file).read()
        lines = content.strip().split("\n")
        assert "ANTHROPIC_API_KEY=sk-secret-123" in lines
        assert "OPENAI_API_KEY=sk-other-456" in lines
        # Verify sorted order
        assert lines[0] == "ANTHROPIC_API_KEY=sk-secret-123"
        assert lines[1] == "OPENAI_API_KEY=sk-other-456"
        # Verify permissions are 0600
        file_stat = os.stat(env_file)
        assert stat.S_IMODE(file_stat.st_mode) == 0o600

    # Verify cleanup after with-block
    assert not os.path.exists(env_file)


def test_env_file_for_cleans_up_when_block_raises():
    env = {"TOKEN": "abc"}

    with pytest.raises(RuntimeError, match="boom"):
        with _env_file_for(env) as env_file:
            assert env_file is not None
            assert os.path.exists(env_file)
            raise RuntimeError("boom")

    # Temp file must be gone even after exception
    assert not os.path.exists(env_file)


def test_env_file_for_empty_dict_is_noop_yields_none():
    with _env_file_for({}) as env_file:
        assert env_file is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_docker.py::test_env_file_for_creates_temp_file_with_key_value_content -v`
Expected: FAIL with `ImportError` or `NameError` — `_env_file_for` not defined

- [ ] **Step 4: Implement `_env_file_for` in `src/aisbox/docker.py`**

Add these imports near the top of `docker.py`:

```python
import tempfile
from contextlib import contextmanager
```

(`import os` and `from collections.abc import Callable, Iterator` already exist in the file.)

Add the `_env_file_for` function before `container_command`:

```python
@contextmanager
def _env_file_for(env: dict[str, str]) -> Iterator[str | None]:
    """Write env vars to a temp file and yield the path.

    The file is created with 0600 permissions and deleted on context exit.
    Yields ``None`` when *env* is empty (no temp file is created).
    """
    if not env:
        yield None
        return

    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            prefix="aisbox-env-",
        )
        os.chmod(tmp.name, 0o600)
        for key in sorted(env):
            tmp.write(f"{key}={env[key]}\n")
        tmp.close()
        yield tmp.name
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp.name)
            except FileNotFoundError:
                pass
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_docker.py::test_env_file_for_creates_temp_file_with_key_value_content tests/test_docker.py::test_env_file_for_cleans_up_when_block_raises tests/test_docker.py::test_env_file_for_empty_dict_is_noop_yields_none -v`
Expected: 3 PASS

- [ ] **Step 6: Commit**

```bash
git add src/aisbox/docker.py tests/test_docker.py
git commit -m "feat: add _env_file_for context manager for secure env-file creation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `container_command` env_file parameter — test then implement

**Files:**
- Modify: `src/aisbox/docker.py`
- Modify: `tests/test_docker.py`

- [ ] **Step 1: Write tests for the new `env_file` parameter**

Append to `tests/test_docker.py`:

```python
def test_container_command_uses_env_file_instead_of_inline_e():
    env = Environment(
        name="demo1",
        agent="claude",
        env={"SECRET": "abc", "TOKEN": "xyz"},
        workspace="/tmp/workspace",
        mounts=[],
        image="aisbox/claude:latest",
        created_at="2026-06-05T00:00:00Z",
    )

    command = container_command(
        env,
        get_agent("claude"),
        "/tmp/config",
        "run",
        "hello",
        env_file="/tmp/aisbox-env-XXXX",
    )

    # Should use --env-file, not -e KEY=VALUE
    assert "--env-file" in command
    assert "/tmp/aisbox-env-XXXX" in command
    assert "SECRET=abc" not in command
    assert "TOKEN=xyz" not in command
    assert "-e" not in command


def test_container_command_falls_back_to_inline_e_when_env_file_is_none():
    env = Environment(
        name="demo1",
        agent="claude",
        env={"SECRET": "abc"},
        workspace="/tmp/workspace",
        mounts=[],
        image="aisbox/claude:latest",
        created_at="2026-06-05T00:00:00Z",
    )

    command = container_command(
        env,
        get_agent("claude"),
        "/tmp/config",
        "run",
        "hello",
        env_file=None,
    )

    # Backward compatible: uses -e KEY=VALUE
    assert "SECRET=abc" in command
    assert "--env-file" not in command


def test_container_command_with_env_file_and_no_env_vars_skips_both():
    env = Environment(
        name="demo1",
        agent="claude",
        env={},
        workspace="/tmp/workspace",
        mounts=[],
        image="aisbox/claude:latest",
        created_at="2026-06-05T00:00:00Z",
    )

    command = container_command(
        env,
        get_agent("claude"),
        "/tmp/config",
        "run",
        "hello",
        env_file="/tmp/aisbox-env-XXXX",
    )

    # No env vars, so neither -e nor --env-file
    assert "--env-file" not in command
    assert "-e" not in command
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_docker.py::test_container_command_uses_env_file_instead_of_inline_e -v`
Expected: FAIL — `--env-file` not found in command (or TypeError for unexpected keyword)

- [ ] **Step 3: Add `env_file` parameter to `container_command`**

In `src/aisbox/docker.py`, change the `container_command` signature to add the parameter:

```python
def container_command(
    env: Environment,
    agent: AgentDefinition,
    config_source: str,
    mode: str,
    prompt: str | None = None,
    retained: bool = False,
    permission_policy: PermissionPolicy = "default",
    env_file: str | None = None,
) -> list[str]:
```

Replace the `-e` loop (lines 158-159):

```python
    for key, value in sorted(env.env.items()):
        command.extend(["-e", f"{key}={value}"])
```

With:

```python
    if env.env:
        if env_file is not None:
            command.extend(["--env-file", env_file])
        else:
            for key, value in sorted(env.env.items()):
                command.extend(["-e", f"{key}={value}"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_docker.py::test_container_command_uses_env_file_instead_of_inline_e tests/test_docker.py::test_container_command_falls_back_to_inline_e_when_env_file_is_none tests/test_docker.py::test_container_command_with_env_file_and_no_env_vars_skips_both -v`
Expected: 3 PASS

Also run the existing container_command tests to confirm no regressions:
Run: `pytest tests/test_docker.py -k "container_command" -v`
Expected: all existing tests PASS (13 tests)

- [ ] **Step 5: Commit**

```bash
git add src/aisbox/docker.py tests/test_docker.py
git commit -m "feat: add env_file parameter to container_command for secure env passing

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Wire `run_container` to use `_env_file_for` — test then implement

**Files:**
- Modify: `src/aisbox/docker.py`
- Modify: `tests/test_docker.py`

- [ ] **Step 1: Write integration test for `run_container` avoiding `-e` leak**

Append to `tests/test_docker.py`:

```python
def test_run_container_uses_env_file_not_inline_e():
    runner = Mock()
    agent = get_agent("claude")
    env = Environment(
        name="demo1",
        agent="claude",
        env={"ANTHROPIC_API_KEY": "sk-secret", "NOT_SECRET": "visible"},
        workspace="/tmp/workspace",
        mounts=[],
        image="aisbox/claude:latest",
        created_at="2026-06-05T00:00:00Z",
    )

    run_container(
        env,
        agent,
        "/tmp/config",
        "run",
        "hello",
        runner,
    )

    command = runner.call_args.args[0]
    # Must NOT contain secrets as -e args
    assert "ANTHROPIC_API_KEY=sk-secret" not in command
    assert "NOT_SECRET=visible" not in command
    assert "-e" not in command
    # Must use --env-file instead
    assert "--env-file" in command
    runner.assert_called_once()
    _, kwargs = runner.call_args
    assert kwargs["check"] is True


def test_run_container_with_empty_env_no_leak_and_no_env_file():
    runner = Mock()
    agent = get_agent("claude")
    env = Environment(
        name="demo1",
        agent="claude",
        env={},
        workspace="/tmp/workspace",
        mounts=[],
        image="aisbox/claude:latest",
        created_at="2026-06-05T00:00:00Z",
    )

    run_container(
        env,
        agent,
        "/tmp/config",
        "run",
        "hello",
        runner,
    )

    command = runner.call_args.args[0]
    assert "--env-file" not in command
    assert "-e" not in command
    runner.assert_called_once_with(command, check=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_docker.py::test_run_container_uses_env_file_not_inline_e -v`
Expected: FAIL — `-e` still present in command, or `--env-file` not found

- [ ] **Step 3: Update `run_container` to use the context manager**

In `src/aisbox/docker.py`, change `run_container` from:

```python
def run_container(
    env: Environment,
    agent: AgentDefinition,
    config_source: str,
    mode: str,
    prompt: str | None = None,
    runner: Runner = default_runner,
    *,
    retained: bool = False,
    permission_policy: PermissionPolicy = "default",
) -> None:
    runner(
        container_command(
            env,
            agent,
            config_source,
            mode,
            prompt,
            retained=retained,
            permission_policy=permission_policy,
        ),
        check=True,
    )
```

To:

```python
def run_container(
    env: Environment,
    agent: AgentDefinition,
    config_source: str,
    mode: str,
    prompt: str | None = None,
    runner: Runner = default_runner,
    *,
    retained: bool = False,
    permission_policy: PermissionPolicy = "default",
) -> None:
    with _env_file_for(env.env) as env_file:
        runner(
            container_command(
                env,
                agent,
                config_source,
                mode,
                prompt,
                retained=retained,
                permission_policy=permission_policy,
                env_file=env_file,
            ),
            check=True,
        )
```

- [ ] **Step 4: Run all docker tests to verify**

Run: `pytest tests/test_docker.py -v`
Expected: all tests PASS (existing + new)

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `pytest tests/ -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/aisbox/docker.py tests/test_docker.py
git commit -m "fix: use --env-file to prevent secret leakage in process listings

Secrets passed via -e KEY=VALUE were visible in /proc/pid/cmdline and
ps aux output. Now writes env vars to a 0600 temp file and passes it
via --env-file, which is cleaned up immediately after docker exits.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Verification

- [ ] Run `pytest tests/ -v` — all tests pass
- [ ] Run `git log --oneline -3` — three clean commits: context manager, parameter, wiring
