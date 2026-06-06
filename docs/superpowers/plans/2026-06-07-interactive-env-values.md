# Interactive Environment Values Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prompt securely for empty environment assignments and align `env set` and `env unset` on required, repeatable `-e/--env` options.

**Architecture:** Keep hidden terminal prompting in `cli.py`, before any command-layer mutation. Add atomic batch mutation functions in `commands.py` so validation finishes before one environment save, then document and regression-test the new command syntax and security boundaries.

**Tech Stack:** Python 3.11, Typer, pytest, Typer `CliRunner`, existing JSON-backed `EnvironmentStore`.

---

## File Structure

- Modify `src/aisbox/cli.py`: resolve empty assignments through hidden prompts, expose repeatable options and help text, and print one redacted status line per key.
- Modify `src/aisbox/commands.py`: replace single-variable mutations with atomic batch set/unset functions.
- Modify `tests/test_cli_core.py`: test `create` prompting, redaction, empty prompt responses, invalid assignments, and CLI help.
- Modify `tests/test_cli_mutation.py`: test repeatable set/unset options, atomic failures, duplicates, and removed positional syntax.
- Modify `README.md`: update authentication, security guidance, and command examples.
- Modify `tests/test_repository_docs.py`: enforce new examples and prompting/security documentation.

### Task 1: Add Interactive Assignment Resolution

**Files:**
- Modify: `tests/test_cli_core.py`
- Modify: `src/aisbox/cli.py`

- [ ] **Step 1: Write failing create prompt tests**

Add tests that invoke `create` with `CliRunner` input:

```python
def test_create_prompts_for_empty_env_values(tmp_path, monkeypatch):
    home = tmp_path / "aisbox-home"
    monkeypatch.setenv("AISBOX_HOME", str(home))
    monkeypatch.setattr("aisbox.commands.build_image", lambda agent: None)

    result = runner.invoke(
        app,
        [
            "create",
            "-n",
            "demo1",
            "-a",
            "claude",
            "-e",
            "ANTHROPIC_API_KEY=",
            "-e",
            "NOT_SENSITIVE=visible",
        ],
        input="prompted-secret\n",
    )

    assert result.exit_code == 0
    assert "ANTHROPIC_API_KEY" in result.stdout
    assert "prompted-secret" not in result.stdout
    assert "visible" not in result.stdout
    env = EnvironmentStore().load("demo1")
    assert env.env == {
        "ANTHROPIC_API_KEY": "prompted-secret",
        "NOT_SENSITIVE": "visible",
    }


def test_create_accepts_empty_prompt_response(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    monkeypatch.setattr("aisbox.commands.build_image", lambda agent: None)

    result = runner.invoke(
        app,
        ["create", "-n", "demo1", "-a", "claude", "-e", "TOKEN="],
        input="\n",
    )

    assert result.exit_code == 0
    assert EnvironmentStore().load("demo1").env["TOKEN"] == ""
```

Also test that an invalid key such as `BAD-KEY=` exits through `Error:` without
prompting, creating the environment, or emitting a traceback.

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```bash
.venv/bin/pytest tests/test_cli_core.py -q
```

Expected: FAIL because `KEY=` is currently stored directly and no prompt is
shown.

- [ ] **Step 3: Implement the CLI resolver**

Import `parse_env_assignment` and add:

```python
def resolve_env_assignments(assignments: list[str]) -> list[str]:
    resolved = []
    for assignment in assignments:
        key, value = parse_env_assignment(assignment)
        if value == "":
            value = typer.prompt(f"Value for {key}", hide_input=True, default="")
        resolved.append(f"{key}={value}")
    return resolved
```

Call the helper inside `create()` before `create_environment()`. Catch
`AisboxError` with the existing `handle_error()` path. Ensure all assignment
validation and prompting complete before `create_environment()` is called.

- [ ] **Step 4: Run focused tests and verify pass**

Run:

```bash
.venv/bin/pytest tests/test_cli_core.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the create prompt behavior**

```bash
git add src/aisbox/cli.py tests/test_cli_core.py
git commit -m "feat: prompt for empty environment values"
```

### Task 2: Add Atomic Batch Environment Mutation

**Files:**
- Modify: `tests/test_cli_mutation.py`
- Modify: `src/aisbox/commands.py`

- [ ] **Step 1: Write failing command-layer batch tests**

Import `set_env_vars`, `unset_env_vars`, and `EnvironmentStore`. Add tests that
create stored environments directly and assert:

```python
def test_set_env_vars_sets_multiple_values_atomically(tmp_path):
    store = EnvironmentStore(tmp_path / "home")
    env = Environment(
        name="demo1",
        agent="claude",
        env={"EXISTING": "old"},
        workspace=str(tmp_path),
        mounts=[],
        image="aisbox/claude:latest",
        created_at="2026-06-07T00:00:00Z",
    )
    store.save(env)

    keys = set_env_vars(
        "demo1",
        ["TOKEN=abc", "EXISTING=new", "TOKEN=final"],
        store=store,
    )

    assert keys == ["TOKEN", "EXISTING", "TOKEN"]
    assert store.load("demo1").env == {"EXISTING": "new", "TOKEN": "final"}
```

Add atomic-failure tests proving an invalid set assignment leaves the original
mapping unchanged. Add unset tests proving multiple keys are removed together
and an invalid, missing, or duplicate key leaves all original variables
unchanged.

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```bash
.venv/bin/pytest tests/test_cli_mutation.py -q
```

Expected: FAIL because the batch functions do not exist.

- [ ] **Step 3: Implement batch command functions**

Add the batch functions alongside the existing single-item functions:

```python
def set_env_vars(
    name: str,
    assignments: list[str],
    store: EnvironmentStore | None = None,
) -> list[str]:
    store = store or EnvironmentStore()
    parsed = [parse_env_assignment(assignment) for assignment in assignments]
    env = store.load(name)
    for key, value in parsed:
        env.env[key] = value
    store.save(env)
    return [key for key, _ in parsed]


def unset_env_vars(
    name: str,
    keys: list[str],
    store: EnvironmentStore | None = None,
) -> list[str]:
    store = store or EnvironmentStore()
    validated = [parse_env_assignment(f"{key}=ignored")[0] for key in keys]
    if len(validated) != len(set(validated)):
        raise AisboxError("Environment variable keys must not be repeated")
    env = store.load(name)
    for key in validated:
        if key not in env.env:
            raise AisboxError(f"Environment variable is not set: {key}")
    for key in validated:
        del env.env[key]
    store.save(env)
    return validated
```

Parsing must occur before loading or mutating, and all existence checks must
occur before deletion. Keep the existing single-item functions until Task 3 so
the CLI remains operational between commits.

- [ ] **Step 4: Run focused tests and verify pass**

Run:

```bash
.venv/bin/pytest tests/test_cli_mutation.py -q
```

Expected: PASS. Existing CLI tests continue using the retained single-item
functions, and the new direct batch tests pass.

- [ ] **Step 5: Commit the command-layer batch behavior**

```bash
git add src/aisbox/commands.py tests/test_cli_mutation.py
git commit -m "feat: batch environment variable mutations"
```

### Task 3: Replace Positional Mutation Syntax With Repeatable Options

**Files:**
- Modify: `tests/test_cli_mutation.py`
- Modify: `tests/test_cli_core.py`
- Modify: `src/aisbox/cli.py`

- [ ] **Step 1: Write failing CLI syntax and help tests**

Update mutation tests to use:

```python
set_result = runner.invoke(
    app,
    [
        "env",
        "set",
        "-n",
        "demo1",
        "-e",
        "TOKEN=",
        "-e",
        "MODE=explicit",
    ],
    input="prompted\n",
)
unset_result = runner.invoke(
    app,
    ["env", "unset", "-n", "demo1", "-e", "TOKEN", "-e", "MODE"],
)
```

Assert both keys are changed, one `Set`/`Unset` line is printed per option, and
neither value appears in output. Add tests that old positional forms exit
nonzero. Add `--help` assertions checking `-e`, `--env`, repeatability, and
prompt behavior for `create`, `env set`, and `env unset`.

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```bash
.venv/bin/pytest tests/test_cli_mutation.py tests/test_cli_core.py -q
```

Expected: FAIL because mutation commands still require one positional item and
do not expose batch output/help.

- [ ] **Step 3: Implement the new CLI command signatures**

Import `set_env_vars` and `unset_env_vars`, removing old imports. Define:

```python
@env_app.command("set")
def env_set(
    env: list[str] = typer.Option(
        ...,
        "-e",
        "--env",
        help="Set KEY=VALUE; an empty value prompts without echo.",
    ),
    name: str | None = typer.Option(None, "-n", "--name"),
) -> None:
    effective_name = effective_environment_name(name)
    try:
        assignments = resolve_env_assignments(env)
        keys = set_env_vars(effective_name, assignments)
    except AisboxError as exc:
        handle_error(exc)
    for key in keys:
        typer.echo(f"Set {key}")


@env_app.command("unset")
def env_unset(
    env: list[str] = typer.Option(
        ...,
        "-e",
        "--env",
        help="Unset an environment variable key; repeat for multiple keys.",
    ),
    name: str | None = typer.Option(None, "-n", "--name"),
) -> None:
    effective_name = effective_environment_name(name)
    try:
        keys = unset_env_vars(effective_name, env)
    except AisboxError as exc:
        handle_error(exc)
    for key in keys:
        typer.echo(f"Unset {key}")
```

Add equivalent help text to `create`'s `env` option. Keep `-e/--env` required
for `env set` and `env unset`, but optional for `create`.

Remove `set_env_var()` and `unset_env_var()` from `commands.py` after the CLI
no longer imports them.

- [ ] **Step 4: Run focused tests and verify pass**

Run:

```bash
.venv/bin/pytest tests/test_cli_mutation.py tests/test_cli_core.py -q
```

Expected: PASS.

- [ ] **Step 5: Verify rendered CLI help**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m aisbox.cli create --help
PYTHONPATH=src .venv/bin/python -m aisbox.cli env set --help
PYTHONPATH=src .venv/bin/python -m aisbox.cli env unset --help
```

Expected: each command documents `-e/--env`; set/create describe hidden
prompting and unset describes repeatability.

- [ ] **Step 6: Commit the aligned CLI**

```bash
git add src/aisbox/cli.py tests/test_cli_core.py tests/test_cli_mutation.py
git commit -m "feat: align environment mutation options"
```

### Task 4: Update Maintained Documentation

**Files:**
- Modify: `tests/test_repository_docs.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing repository documentation assertions**

Extend the README tests to require:

```python
for text in [
    "aisbox create -n demo1 -a claude -e ANTHROPIC_API_KEY=",
    "aisbox env set -n demo1 -e OPENAI_API_KEY=",
    "aisbox env unset -n demo1 -e OPENAI_API_KEY",
    "hidden prompt",
    "Press Enter",
    "stored unencrypted",
]:
    assert text in readme

assert "aisbox env set -n demo1 KEY=VALUE" not in readme
assert "aisbox env unset -n demo1 KEY" not in readme
```

Also assert the security section explains that prompted values are excluded
from shell history and normal command-line process inspection, while explicit
non-empty command-line values retain the existing exposure warning.

- [ ] **Step 2: Run documentation tests and verify failure**

Run:

```bash
.venv/bin/pytest tests/test_repository_docs.py tests/test_cli_core.py -q
```

Expected: FAIL on old README examples and missing prompt guidance.

- [ ] **Step 3: Update README authentication and command sections**

Use examples equivalent to:

```bash
aisbox create -n demo1 -a claude -e ANTHROPIC_API_KEY=
aisbox env set -n demo1 -e OPENAI_API_KEY=
aisbox env set -n demo1 -e LOG_LEVEL=debug -e FEATURE_FLAG=enabled
aisbox env unset -n demo1 -e LOG_LEVEL -e FEATURE_FLAG
```

Explain:

- `KEY=` opens one hidden prompt.
- pressing Enter stores an empty string;
- prompted values avoid shell history and normal command-line process
  inspection;
- explicit values remain supported but retain the existing exposure warning;
- all values remain stored unencrypted in managed state.

- [ ] **Step 4: Run documentation tests and verify pass**

Run:

```bash
.venv/bin/pytest tests/test_repository_docs.py tests/test_cli_core.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit documentation**

```bash
git add README.md tests/test_repository_docs.py
git commit -m "docs: explain interactive environment values"
```

### Task 5: Full Verification And Push

**Files:**
- Verify all modified files.

- [ ] **Step 1: Run formatting and whitespace checks**

Run:

```bash
git diff --check main...HEAD
```

Expected: no output.

- [ ] **Step 2: Run the full test suite**

Run:

```bash
.venv/bin/pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Inspect the final branch**

Run:

```bash
git status --short --branch
git log --oneline --decorate main..HEAD
git diff --stat main...HEAD
```

Expected: clean `feat/interactive-env-values` worktree containing the design,
implementation plan, implementation, tests, and documentation commits.

- [ ] **Step 4: Push the feature branch**

```bash
git push -u origin feat/interactive-env-values
```

Expected: the remote branch is created and upstream tracking is configured. Do
not create a pull request.
