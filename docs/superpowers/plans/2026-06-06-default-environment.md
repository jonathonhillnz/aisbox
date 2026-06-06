# Default Environment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add `aisbox set default -n <env>` and let environment-specific commands omit `-n` by using the saved default, while explicit `-n` always overrides it.

**Architecture:** Store aisbox-level settings in `<AISBOX_HOME>/settings.json` with `default_environment` as the first key. Add store and command helpers for default management, then keep CLI command handlers responsible for resolving optional names into concrete names before calling existing behavior functions.

**Tech Stack:** Python 3.11, Typer, pytest, `pathlib.Path`, JSON state in `EnvironmentStore`.

---

## File Structure

- Modify `src/aisbox/store.py`: add generic settings read/write helpers and default-environment methods; clear default during deletion.
- Modify `src/aisbox/commands.py`: add `set_default_environment()` and `resolve_environment_name()` helpers.
- Modify `src/aisbox/cli.py`: add top-level `set` Typer group, wire `set default`, make environment-specific `-n` options optional, and resolve defaults centrally.
- Modify `tests/test_store.py`: cover settings persistence, validation, and clearing behavior.
- Modify `tests/test_cli_runtime.py`: cover run default and explicit override.
- Modify `tests/test_cli_core.py`: cover `set default`, missing default error, delete clearing default, and README command list.
- Modify `README.md`: document `aisbox set default -n demo1` and default-backed commands.

---

### Task 1: Store Settings And Default Persistence

**Files:**
- Modify: `tests/test_store.py`
- Modify: `src/aisbox/store.py`

- [x] **Step 1: Write failing store tests**

Add these tests to `tests/test_store.py`:

```python
def test_set_and_load_default_environment(aisbox_home, tmp_path):
    store = EnvironmentStore()
    store.save(make_env(tmp_path))

    store.set_default_environment("demo1")

    assert store.load_default_environment() == "demo1"
    payload = json.loads((aisbox_home / "settings.json").read_text(encoding="utf-8"))
    assert payload == {"default_environment": "demo1"}


def test_set_default_environment_rejects_missing_environment(aisbox_home):
    store = EnvironmentStore()

    with pytest.raises(AisboxError, match="Environment does not exist: missing"):
        store.set_default_environment("missing")

    assert not (aisbox_home / "settings.json").exists()


def test_delete_default_environment_clears_only_default_setting(aisbox_home, tmp_path):
    store = EnvironmentStore()
    store.save(make_env(tmp_path))
    store.write_settings({"default_environment": "demo1", "future_setting": "kept"})

    store.delete("demo1")

    assert store.read_settings() == {"future_setting": "kept"}


def test_load_default_environment_rejects_unsafe_persisted_name(aisbox_home):
    store = EnvironmentStore()
    aisbox_home.mkdir(parents=True)
    (aisbox_home / "settings.json").write_text(
        json.dumps({"default_environment": "../demo"}),
        encoding="utf-8",
    )

    with pytest.raises(AisboxError, match=r"Environment name must match"):
        store.load_default_environment()
```

- [x] **Step 2: Run store tests to verify failure**

Run: `.venv/bin/pytest tests/test_store.py -q`

Expected: FAIL because `EnvironmentStore` has no settings/default methods.

- [x] **Step 3: Implement store settings helpers**

Add these methods to `EnvironmentStore` in `src/aisbox/store.py`:

```python
    def settings_path(self) -> Path:
        return self.root / "settings.json"

    def read_settings(self) -> dict[str, object]:
        path = self.settings_path()
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise AisboxError("Settings file must contain a JSON object")
        return payload

    def write_settings(self, settings: dict[str, object]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.settings_path().write_text(
            json.dumps(settings, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def set_default_environment(self, name: str) -> None:
        name = validate_env_name(name)
        if not self.exists(name):
            raise AisboxError(f"Environment does not exist: {name}")
        settings = self.read_settings()
        settings["default_environment"] = name
        self.write_settings(settings)

    def load_default_environment(self) -> str | None:
        settings = self.read_settings()
        name = settings.get("default_environment")
        if name is None:
            return None
        if not isinstance(name, str):
            raise AisboxError("Default environment setting must be a string")
        name = validate_env_name(name)
        if not self.exists(name):
            raise AisboxError(f"Environment does not exist: {name}")
        return name

    def clear_default_environment(self) -> None:
        settings = self.read_settings()
        if "default_environment" not in settings:
            return
        del settings["default_environment"]
        self.write_settings(settings)
```

Update `delete()` so it clears the default before removing the environment:

```python
    def delete(self, name: str) -> None:
        if not self.exists(name):
            raise AisboxError(f"Environment does not exist: {name}")
        current_default = self.load_default_environment()
        if current_default == validate_env_name(name):
            self.clear_default_environment()
        shutil.rmtree(self.env_dir(name))
```

- [x] **Step 4: Run store tests to verify pass**

Run: `.venv/bin/pytest tests/test_store.py -q`

Expected: PASS.

---

### Task 2: Command Helpers For Default Resolution

**Files:**
- Modify: `tests/test_store.py`
- Modify: `src/aisbox/commands.py`

- [x] **Step 1: Write failing command helper tests**

Add this import to `tests/test_store.py`:

```python
from aisbox.commands import resolve_environment_name, set_default_environment
```

Add these tests:

```python
def test_command_resolve_environment_name_prefers_explicit_name(aisbox_home, tmp_path):
    store = EnvironmentStore()
    store.save(make_env(tmp_path))
    env2 = make_env(tmp_path)
    env2.name = "demo2"
    store.save(env2)
    store.set_default_environment("demo1")

    assert resolve_environment_name("demo2", store) == "demo2"


def test_command_resolve_environment_name_uses_default(aisbox_home, tmp_path):
    store = EnvironmentStore()
    store.save(make_env(tmp_path))
    store.set_default_environment("demo1")

    assert resolve_environment_name(None, store) == "demo1"


def test_command_resolve_environment_name_requires_name_or_default(aisbox_home):
    store = EnvironmentStore()

    with pytest.raises(
        AisboxError,
        match="No environment specified and no default environment is set",
    ):
        resolve_environment_name(None, store)


def test_command_set_default_environment_returns_name(aisbox_home, tmp_path):
    store = EnvironmentStore()
    store.save(make_env(tmp_path))

    assert set_default_environment("demo1", store) == "demo1"
    assert store.load_default_environment() == "demo1"
```

- [x] **Step 2: Run focused tests to verify failure**

Run: `.venv/bin/pytest tests/test_store.py -q`

Expected: FAIL because `commands.py` does not define the new helpers.

- [x] **Step 3: Implement command helpers**

Add to `src/aisbox/commands.py` after `delete_environment()`:

```python
def set_default_environment(name: str, store: EnvironmentStore | None = None) -> str:
    store = store or EnvironmentStore()
    name = validate_env_name(name)
    store.set_default_environment(name)
    return name


def resolve_environment_name(
    name: str | None,
    store: EnvironmentStore | None = None,
) -> str:
    store = store or EnvironmentStore()
    if name is not None:
        return validate_env_name(name)
    default_name = store.load_default_environment()
    if default_name is None:
        raise AisboxError("No environment specified and no default environment is set")
    return default_name
```

- [x] **Step 4: Run focused tests to verify pass**

Run: `.venv/bin/pytest tests/test_store.py -q`

Expected: PASS.

---

### Task 3: CLI Default Selection

**Files:**
- Modify: `tests/test_cli_core.py`
- Modify: `tests/test_cli_runtime.py`
- Modify: `src/aisbox/cli.py`

- [x] **Step 1: Write failing CLI tests**

Add these tests to `tests/test_cli_core.py`:

```python
def test_set_default_environment_command(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    monkeypatch.setattr("aisbox.commands.build_image", lambda agent: None)
    runner.invoke(app, ["create", "-n", "demo1", "-a", "claude"])

    result = runner.invoke(app, ["set", "default", "-n", "demo1"])

    assert result.exit_code == 0
    assert "Default environment set to demo1" in result.stdout


def test_environment_command_without_name_and_without_default_errors_cleanly(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))

    result = runner.invoke(app, ["inspect"])

    assert result.exit_code == 1
    assert "No environment specified and no default environment is set" in result.stderr
    assert "Traceback" not in result.stderr


def test_delete_default_environment_clears_cli_default(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    monkeypatch.setattr("aisbox.commands.build_image", lambda agent: None)
    runner.invoke(app, ["create", "-n", "demo1", "-a", "claude"])
    runner.invoke(app, ["set", "default", "-n", "demo1"])

    deleted = runner.invoke(app, ["delete", "--force"])
    inspected = runner.invoke(app, ["inspect"])

    assert deleted.exit_code == 0
    assert "Deleted demo1" in deleted.stdout
    assert inspected.exit_code == 1
    assert "No environment specified and no default environment is set" in inspected.stderr
```

Add these tests to `tests/test_cli_runtime.py`:

```python
def test_run_uses_default_environment_when_name_omitted(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    runner.invoke(app, ["set", "default", "-n", "demo1"])
    runner_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", runner_mock)

    result = runner.invoke(app, ["run", "--", "hello"])

    assert result.exit_code == 0
    env, agent, config_source, mode, prompt = runner_mock.call_args.args
    assert env.name == "demo1"
    assert agent.name == "claude"
    assert config_source.endswith("/config")
    assert mode == "run"
    assert prompt == "hello"


def test_run_explicit_name_overrides_default_environment(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr("aisbox.commands.build_image", lambda agent: None)
    runner.invoke(app, ["create", "-n", "demo2", "-a", "claude"])
    runner.invoke(app, ["set", "default", "-n", "demo1"])
    runner_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", runner_mock)

    result = runner.invoke(app, ["run", "-n", "demo2", "--", "hello"])

    assert result.exit_code == 0
    env = runner_mock.call_args.args[0]
    assert env.name == "demo2"
```

- [x] **Step 2: Run focused CLI tests to verify failure**

Run: `.venv/bin/pytest tests/test_cli_core.py tests/test_cli_runtime.py -q`

Expected: FAIL because `set default` does not exist and `-n` is still required.

- [x] **Step 3: Implement CLI command group and optional-name resolution**

In `src/aisbox/cli.py`, import the new command helpers:

```python
    resolve_environment_name,
    set_default_environment as set_default_environment_command,
```

Add the Typer group near the existing app declarations:

```python
set_app = typer.Typer(no_args_is_help=True)
app.add_typer(set_app, name="set")
```

Add a central CLI helper after `handle_error()`:

```python
def effective_environment_name(name: str | None) -> str:
    try:
        return resolve_environment_name(name)
    except AisboxError as exc:
        handle_error(exc)
    raise typer.Exit(code=1)
```

Add the command:

```python
@set_app.command("default")
def set_default(name: str = typer.Option(..., "-n", "--name")) -> None:
    try:
        default_name = set_default_environment_command(name)
    except AisboxError as exc:
        handle_error(exc)
    typer.echo(f"Default environment set to {default_name}")
```

For each environment-specific CLI handler, change `name: str = typer.Option(..., "-n", "--name")` to `name: str | None = typer.Option(None, "-n", "--name")`, then call the existing command behavior with `effective_environment_name(name)`. For `delete`, resolve the effective name before confirmation so the prompt and success message use the concrete name:

```python
def delete(
    name: str | None = typer.Option(None, "-n", "--name"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    effective_name = effective_environment_name(name)
    if not force and not typer.confirm(f"Delete environment {effective_name}"):
        raise typer.Exit(code=1)
    try:
        delete_environment(effective_name)
    except AisboxError as exc:
        handle_error(exc)
    typer.echo(f"Deleted {effective_name}")
```

- [x] **Step 4: Run focused CLI tests to verify pass**

Run: `.venv/bin/pytest tests/test_cli_core.py tests/test_cli_runtime.py -q`

Expected: PASS.

---

### Task 4: README And Full Verification

**Files:**
- Modify: `README.md`
- Modify: `tests/test_cli_core.py`

- [x] **Step 1: Update README command test expectation**

In `tests/test_cli_core.py`, add `"aisbox set default"` to the `command` list in `test_readme_documents_primary_commands`.

- [x] **Step 2: Update README examples**

In `README.md`, add this command after the create examples:

```bash
aisbox set default -n demo1
```

Change the run example to show the default path:

```bash
aisbox run -- "summarize this repository"
```

Keep at least one explicit `-n` example for attach/shell/inspect/rebuild/mount/unmount/env/delete so the override path remains documented.

- [x] **Step 3: Run README test**

Run: `.venv/bin/pytest tests/test_cli_core.py::test_readme_documents_primary_commands -q`

Expected: PASS.

- [x] **Step 4: Run full test suite**

Run: `.venv/bin/pytest -q`

Expected: PASS.

- [x] **Step 5: Review git diff**

Run: `git diff -- src/aisbox/store.py src/aisbox/commands.py src/aisbox/cli.py tests/test_store.py tests/test_cli_core.py tests/test_cli_runtime.py README.md`

Expected: Diff only contains default-environment feature changes and README updates.
