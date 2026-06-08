# Agent Permission Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `aisbox run --permission-policy default|auto|bypass` and teach the local coagent skill how to ask for and recommend permission policies.

**Architecture:** Store policy-specific run command suffixes in `AgentDefinition`, thread the selected policy through `cli.run -> commands.run_environment -> docker.run_container -> docker.container_command`, and leave saved `Environment` state unchanged. Update README and `skills/aisbox-coagent/SKILL.md` so users and local agents understand when to choose `default`, `auto`, or `bypass`.

**Tech Stack:** Python 3.11+, Typer, pytest, Docker command construction, Markdown skills and repository docs.

---

## File Structure

- Modify `src/aisbox/models.py`: add the `PermissionPolicy` type alias and policy mapping field to `AgentDefinition`.
- Modify `src/aisbox/agents.py`: define each agent's `run_permission_commands`.
- Modify `src/aisbox/docker.py`: select the policy-specific run command when building `docker run`.
- Modify `src/aisbox/commands.py`: accept and pass permission policy through runtime orchestration.
- Modify `src/aisbox/cli.py`: expose `--permission-policy` on `aisbox run`.
- Modify `tests/test_agents.py`: assert each agent exposes the expected policy mappings.
- Modify `tests/test_docker.py`: assert Docker commands include the correct policy flags before the prompt.
- Modify `tests/test_cli_runtime.py`: assert CLI passes the selected policy to `run_container` and does not save it.
- Modify `tests/test_repository_docs.py`: assert README and skill docs cover permission policy behavior.
- Modify `README.md`: document the CLI flag, mapping, and safety tradeoff.
- Modify `skills/aisbox-coagent/SKILL.md`: add permission policy selection to the delegation workflow.

### Task 1: Agent Model And Mapping Tests

**Files:**
- Modify: `src/aisbox/models.py`
- Modify: `src/aisbox/agents.py`
- Test: `tests/test_agents.py`

- [ ] **Step 1: Write failing tests for policy mappings**

Add these assertions to the existing agent definition tests in `tests/test_agents.py`:

```python
def test_get_agent_returns_claude_definition():
    agent = get_agent("claude")

    assert agent.name == "claude"
    assert agent.image == "aisbox/claude:latest"
    assert agent.config_path == "/home/aisbox"
    assert agent.run_command == ["claude", "-p"]
    assert agent.run_permission_commands == {
        "default": ["claude", "-p"],
        "auto": ["claude", "-p", "--permission-mode", "auto"],
        "bypass": ["claude", "-p", "--dangerously-skip-permissions"],
    }
    assert agent.attach_command == ["claude"]
    assert "npm install -g @anthropic-ai/claude-code" in agent.dockerfile


def test_get_agent_returns_codex_definition():
    agent = get_agent("codex")

    assert agent.name == "codex"
    assert agent.image == "aisbox/codex:latest"
    assert agent.config_path == "/home/aisbox"
    assert agent.run_command == ["codex", "exec"]
    assert agent.run_permission_commands == {
        "default": ["codex", "exec"],
        "auto": [
            "codex",
            "exec",
            "--ask-for-approval",
            "never",
            "--sandbox",
            "workspace-write",
        ],
        "bypass": [
            "codex",
            "exec",
            "--dangerously-bypass-approvals-and-sandbox",
        ],
    }
    assert agent.attach_command == ["codex"]
    assert "npm install -g @openai/codex" in agent.dockerfile


def test_get_agent_returns_opencode_definition():
    agent = get_agent("opencode")

    assert agent.name == "opencode"
    assert agent.image == "aisbox/opencode:latest"
    assert agent.config_path == "/home/aisbox"
    assert agent.run_command == ["opencode", "run"]
    assert agent.run_permission_commands == {
        "default": ["opencode", "run"],
        "auto": ["opencode", "run", "--dangerously-skip-permissions"],
        "bypass": ["opencode", "run", "--dangerously-skip-permissions"],
    }
    assert agent.attach_command == ["opencode"]
    assert "npm install -g opencode-ai@latest" in agent.dockerfile
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/pytest tests/test_agents.py -v
```

Expected: the three updated tests fail with `AttributeError: 'AgentDefinition' object has no attribute 'run_permission_commands'`.

- [ ] **Step 3: Add model field and agent mappings**

In `src/aisbox/models.py`, add the type alias and field:

```python
from typing import Literal


PermissionPolicy = Literal["default", "auto", "bypass"]
```

Update `AgentDefinition`:

```python
@dataclass(frozen=True)
class AgentDefinition:
    name: str
    image: str
    config_path: str
    dockerfile: str
    run_command: list[str]
    attach_command: list[str]
    run_permission_commands: dict[PermissionPolicy, list[str]]
    shell_command: list[str] = field(default_factory=lambda: ["/bin/bash"])
```

In `src/aisbox/agents.py`, add `run_permission_commands` to each `AgentDefinition` using the mappings from Step 1.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/pytest tests/test_agents.py -v
```

Expected: all tests in `tests/test_agents.py` pass.

- [ ] **Step 5: Commit**

```bash
git add src/aisbox/models.py src/aisbox/agents.py tests/test_agents.py
git commit -m "feat: define agent permission policies"
```

### Task 2: Docker Command Policy Selection

**Files:**
- Modify: `src/aisbox/docker.py`
- Test: `tests/test_docker.py`

- [ ] **Step 1: Write failing Docker command tests**

Add these tests near the existing run command tests in `tests/test_docker.py`:

Update imports first:

```python
from aisbox.errors import AisboxError
from aisbox.models import (
    AgentDefinition,
    DockerContainer,
    Environment,
    Mount,
    RetainedSession,
)
```

```python
def test_container_command_runs_claude_with_auto_permission_policy():
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
        permission_policy="auto",
    )

    assert command[-4:] == ["-p", "--permission-mode", "auto", "hello"]


def test_container_command_runs_claude_with_bypass_permission_policy():
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
        permission_policy="bypass",
    )

    assert command[-3:] == ["-p", "--dangerously-skip-permissions", "hello"]


def test_container_command_runs_codex_with_auto_permission_policy():
    env = Environment(
        name="demo1",
        agent="codex",
        env={},
        workspace="/tmp/workspace",
        mounts=[],
        image="aisbox/codex:latest",
        created_at="2026-06-05T00:00:00Z",
    )

    command = container_command(
        env,
        get_agent("codex"),
        "/tmp/config",
        "run",
        "hello",
        permission_policy="auto",
    )

    assert command[-6:] == [
        "exec",
        "--ask-for-approval",
        "never",
        "--sandbox",
        "workspace-write",
        "hello",
    ]


def test_container_command_runs_codex_with_bypass_permission_policy():
    env = Environment(
        name="demo1",
        agent="codex",
        env={},
        workspace="/tmp/workspace",
        mounts=[],
        image="aisbox/codex:latest",
        created_at="2026-06-05T00:00:00Z",
    )

    command = container_command(
        env,
        get_agent("codex"),
        "/tmp/config",
        "run",
        "hello",
        permission_policy="bypass",
    )

    assert command[-3:] == [
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "hello",
    ]


def test_container_command_runs_opencode_with_auto_permission_policy():
    command = container_command(
        opencode_environment(),
        get_agent("opencode"),
        "/tmp/config",
        "run",
        "hello",
        permission_policy="auto",
    )

    assert command[-4:] == [
        "opencode",
        "run",
        "--dangerously-skip-permissions",
        "hello",
    ]


def test_container_command_runs_opencode_with_bypass_permission_policy():
    command = container_command(
        opencode_environment(),
        get_agent("opencode"),
        "/tmp/config",
        "run",
        "hello",
        permission_policy="bypass",
    )

    assert command[-4:] == [
        "opencode",
        "run",
        "--dangerously-skip-permissions",
        "hello",
    ]


def test_container_command_rejects_unsupported_permission_policy():
    agent = AgentDefinition(
        name="custom",
        image="aisbox/custom:latest",
        config_path="/home/aisbox",
        dockerfile="FROM ubuntu:24.04\n",
        run_command=["custom", "run"],
        attach_command=["custom"],
        run_permission_commands={"default": ["custom", "run"]},
    )
    env = Environment(
        name="demo1",
        agent="custom",
        env={},
        workspace="/tmp/workspace",
        mounts=[],
        image="aisbox/custom:latest",
        created_at="2026-06-05T00:00:00Z",
    )

    with pytest.raises(AisboxError, match="Permission policy 'auto' is not supported"):
        container_command(
            env,
            agent,
            "/tmp/config",
            "run",
            "hello",
            permission_policy="auto",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/pytest tests/test_docker.py -v
```

Expected: new policy tests fail with `TypeError: container_command() got an unexpected keyword argument 'permission_policy'`.

- [ ] **Step 3: Implement policy selection in Docker command construction**

In `src/aisbox/docker.py`, import the error and type:

```python
from aisbox.errors import AisboxError
from aisbox.models import AgentDefinition, DockerContainer, Environment, PermissionPolicy
```

Update `container_command` signature:

```python
def container_command(
    env: Environment,
    agent: AgentDefinition,
    config_source: str,
    mode: str,
    prompt: str | None = None,
    retained: bool = False,
    permission_policy: PermissionPolicy = "default",
) -> list[str]:
```

Update the run branch:

```python
    if mode == "run":
        try:
            run_command = agent.run_permission_commands[permission_policy]
        except KeyError as exc:
            raise AisboxError(
                f"Permission policy '{permission_policy}' is not supported "
                f"for agent: {agent.name}"
            ) from exc
        command.extend(run_command)
        if prompt is not None:
            command.append(prompt)
```

Update `run_container` signature and call:

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

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/pytest tests/test_docker.py -v
```

Expected: all tests in `tests/test_docker.py` pass.

- [ ] **Step 5: Commit**

```bash
git add src/aisbox/docker.py tests/test_docker.py
git commit -m "feat: apply permission policy to run commands"
```

### Task 3: CLI And Command Threading

**Files:**
- Modify: `src/aisbox/commands.py`
- Modify: `src/aisbox/cli.py`
- Test: `tests/test_cli_runtime.py`

- [ ] **Step 1: Write failing CLI tests**

Add these tests near `test_run_builds_non_interactive_docker_command` in `tests/test_cli_runtime.py`:

```python
def test_run_passes_permission_policy_to_container(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    runner_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", runner_mock)

    result = runner.invoke(
        app,
        ["run", "-n", "demo1", "--permission-policy", "auto", "--", "hello"],
    )

    assert result.exit_code == 0
    assert runner_mock.call_args.kwargs["permission_policy"] == "auto"


def test_run_permission_policy_is_not_saved(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    runner_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", runner_mock)

    result = runner.invoke(
        app,
        ["run", "-n", "demo1", "--permission-policy", "bypass", "--", "hello"],
    )

    assert result.exit_code == 0
    stored_env = EnvironmentStore().load("demo1")
    assert not hasattr(stored_env, "permission_policy")


def test_run_rejects_invalid_permission_policy_without_traceback(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        ["run", "-n", "demo1", "--permission-policy", "invalid", "--", "hello"],
    )

    assert result.exit_code != 0
    assert "Invalid value for '--permission-policy'" in result.stdout
    assert "Traceback" not in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/pytest tests/test_cli_runtime.py::test_run_passes_permission_policy_to_container tests/test_cli_runtime.py::test_run_permission_policy_is_not_saved tests/test_cli_runtime.py::test_run_rejects_invalid_permission_policy_without_traceback -v
```

Expected: tests fail because `--permission-policy` is not a known option.

- [ ] **Step 3: Thread permission policy through commands**

In `src/aisbox/commands.py`, import the type:

```python
from aisbox.models import Environment, Mount, PermissionPolicy, RetainedSession
```

Update `run_environment` signature:

```python
def run_environment(
    name: str,
    mode: str,
    prompt: str | None = None,
    store: EnvironmentStore | None = None,
    *,
    workspace: str | None = None,
    mounts: list[tuple[str, str]] | None = None,
    permission_policy: PermissionPolicy = "default",
) -> None:
```

Update the `run_container` call:

```python
        run_container(
            env,
            agent,
            config_source,
            mode,
            prompt,
            permission_policy=permission_policy,
        )
```

- [ ] **Step 4: Add Typer option**

In `src/aisbox/cli.py`, import `Literal` if not already present:

```python
from typing import Literal
```

Update `run` signature:

```python
    permission_policy: Literal["default", "auto", "bypass"] = typer.Option(
        "default",
        "--permission-policy",
        help=(
            "Agent permission policy for this run: default, auto, or bypass."
        ),
    ),
```

Pass it into `run_environment`:

```python
        run_environment(
            effective_name,
            "run",
            prompt,
            workspace=workspace,
            mounts=mounts,
            permission_policy=permission_policy,
        )
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/test_cli_runtime.py::test_run_builds_non_interactive_docker_command tests/test_cli_runtime.py::test_run_passes_permission_policy_to_container tests/test_cli_runtime.py::test_run_permission_policy_is_not_saved tests/test_cli_runtime.py::test_run_rejects_invalid_permission_policy_without_traceback -v
```

Expected: all four tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/aisbox/commands.py src/aisbox/cli.py tests/test_cli_runtime.py
git commit -m "feat: expose run permission policy option"
```

### Task 4: README And Repository Documentation Tests

**Files:**
- Modify: `README.md`
- Modify: `tests/test_repository_docs.py`

- [ ] **Step 1: Write failing README coverage test**

Add this test near the other README run/agent documentation tests in `tests/test_repository_docs.py`:

```python
def test_readme_documents_run_permission_policy():
    readme = read_text("README.md")
    normalized = " ".join(readme.split())

    for text in [
        "aisbox run --permission-policy auto -- \"update the tests\"",
        "aisbox run --permission-policy bypass -- \"prototype the change\"",
        "`default` keeps the agent's default approval behavior",
        "`auto` is recommended for non-interactive write-capable runs",
        "`bypass` disables agent-level approval prompts",
        "Claude Code",
        "`--permission-mode auto`",
        "`--dangerously-skip-permissions`",
        "Codex CLI",
        "`--ask-for-approval never --sandbox workspace-write`",
        "`--dangerously-bypass-approvals-and-sandbox`",
        "OpenCode",
        "maps to `--dangerously-skip-permissions`",
    ]:
        assert text in normalized
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/pytest tests/test_repository_docs.py::test_readme_documents_run_permission_policy -v
```

Expected: test fails because README does not mention the new flag yet.

- [ ] **Step 3: Update README**

In `README.md`, add this section after `## Supported Agents` and before `## Authentication`:

````markdown
## Run Permission Policies

`aisbox run` defaults to the selected agent's normal approval behavior:

```bash
aisbox run -- "summarize this repository"
```

For non-interactive tasks that need ordinary writes inside the mounted
workspace, use `auto`:

```bash
aisbox run --permission-policy auto -- "update the tests"
```

Use `bypass` only for trusted repositories and scoped prompts. It disables
agent-level approval prompts as much as the selected agent supports:

```bash
aisbox run --permission-policy bypass -- "prototype the change"
```

Policy mapping:

| Agent | `auto` mapping | `bypass` mapping |
| --- | --- | --- |
| Claude Code | `--permission-mode auto` | `--dangerously-skip-permissions` |
| Codex CLI | `--ask-for-approval never --sandbox workspace-write` | `--dangerously-bypass-approvals-and-sandbox` |
| OpenCode | maps to `--dangerously-skip-permissions` | maps to `--dangerously-skip-permissions` |

`default` keeps the agent's default approval behavior. `auto` is recommended
for non-interactive write-capable runs. `bypass` disables agent-level approval
prompts and should be used only inside trusted aisbox containers with explicit
workspace and mount choices.
````

- [ ] **Step 4: Add command list example**

In the `## Commands` block in `README.md`, add:

```text
aisbox run -n demo1 --permission-policy auto -- "update the tests"
```

Place it near the other `aisbox run` examples and before delete.

- [ ] **Step 5: Run docs tests**

Run:

```bash
.venv/bin/pytest tests/test_repository_docs.py::test_readme_documents_run_permission_policy tests/test_repository_docs.py::test_readme_documents_all_cli_commands tests/test_repository_docs.py::test_readme_commands_keep_lifecycle_workflow_before_delete -v
```

Expected: all three tests pass.

- [ ] **Step 6: Commit**

```bash
git add README.md tests/test_repository_docs.py
git commit -m "docs: document run permission policies"
```

### Task 5: Coagent Skill Update

**Files:**
- Modify: `skills/aisbox-coagent/SKILL.md`
- Modify: `tests/test_repository_docs.py`

- [ ] **Step 1: Write failing skill documentation test**

Add this test to `tests/test_repository_docs.py`:

```python
def test_aisbox_coagent_skill_documents_permission_policy_choice():
    skill = read_text("skills/aisbox-coagent/SKILL.md")
    normalized = " ".join(skill.split())

    for text in [
        "Choose the permission policy — ASK every time.",
        "`default` for clearly read-only work",
        "`auto` for work likely to need normal in-workspace writes",
        "`bypass`",
        "Do not recommend it by default.",
        "aisbox run --permission-policy auto -- \"<prompt>\"",
        "About to use `auto` or `bypass` without operator approval",
        "Using `default` for a write task and causing an approval deadlock",
    ]:
        assert text in normalized
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/pytest tests/test_repository_docs.py::test_aisbox_coagent_skill_documents_permission_policy_choice -v
```

Expected: test fails because the skill does not yet mention permission policy.

- [ ] **Step 3: Update quick reference**

In `skills/aisbox-coagent/SKILL.md`, update the quick reference table:

```markdown
| Need | Command |
| --- | --- |
| Run on the default sandbox | `aisbox run -- "<prompt>"` |
| Run on a named sandbox | `aisbox run -n <name> -- "<prompt>"` |
| Let the coagent see the current repo | add `--workspace .` |
| Allow normal write-capable one-shot work | `aisbox run --permission-policy auto -- "<prompt>"` |
| List sandboxes | `aisbox list` → `name<TAB>agent<TAB>workspace` |
```

- [ ] **Step 4: Update workflow**

Replace Workflow steps 2-5 with:

```markdown
2. **Choose the workspace — ASK every time.** Ask the operator:
   *"Should the coagent see this repo (`--workspace .`), or run against the
   sandbox's own workspace?"* Mounting `--workspace .` exposes the current
   directory to the sandbox and its outbound network — flag that. Default lean:
   sandbox-only. Never decide this silently.

3. **Choose the permission policy — ASK every time.** Infer the likely need
   from the task, recommend one policy, and let the operator decide:
   - Use `default` for clearly read-only work: explain code, inspect files,
     summarize, review, or answer questions.
   - Use `auto` for work likely to need normal in-workspace writes: create
     files, edit code, add tests, generate docs, run write-capable formatters,
     or validate write permissions.
   - Mention `bypass` only when the operator explicitly wants maximum autonomy
     or the task needs broad command execution. Do not recommend it by default.

   Example prompt:
   *"This looks write-capable, so I recommend `--permission-policy auto`. Use
   that, choose `bypass`, or keep the agent default?"*

4. **Resolve the sandbox** (see flowchart). If the operator named one, use
   `-n <name>`. Otherwise **do not look up the default** — just run with no
   `-n` and let the CLI use it. Only run `aisbox list` and ask the operator
   *after* a run fails with `Error: No environment specified and no default
   environment is set`. `aisbox list` shows envs but not which is default, so
   don't try to pick from it pre-emptively.

5. **Run it** and capture stdout/stderr/exit code.

6. **Handle the outcome** (see flowchart). On success, self-check the output
   against the task, summarize it, and **confirm with the operator before
   accepting**. On failure, report stderr and offer to do it yourself.
```

- [ ] **Step 5: Update flowchart labels**

In the DOT flowchart, add a box between the named/default decision and exit:

```dot
    policy [shape=box label="ASK permission policy:\ndefault for read-only,\nauto for likely writes,\nbypass only if requested"];
```

Route default runs through the no-default check first. Route named runs straight
to policy selection, and route successful default resolution to policy
selection:

```dot
    usedefault -> nodefault;
    nodefault -> list [label="yes"];
    nodefault -> policy [label="no"];
    list -> usenamed;
    usenamed -> policy;
    policy -> exit;
```

Keep the no-default failure check after `usedefault`; named runs can go straight to `policy`.

- [ ] **Step 6: Update mistakes and red flags**

Add rows to Common Mistakes:

```markdown
| Using `default` for a write task and causing an approval deadlock | Recommend `auto`, explain why, and ask before running. |
| Silently using `auto` or `bypass` | Ask every time; permission policy is operator-owned. |
```

Add red flags:

```markdown
- About to use `auto` or `bypass` without operator approval → ask first.
- About to delegate a likely write task with `default` after seeing approval-deadlock risk → recommend `auto` and ask.
```

- [ ] **Step 7: Run skill doc test**

Run:

```bash
.venv/bin/pytest tests/test_repository_docs.py::test_aisbox_coagent_skill_documents_permission_policy_choice -v
```

Expected: test passes.

- [ ] **Step 8: Commit**

```bash
git add skills/aisbox-coagent/SKILL.md tests/test_repository_docs.py
git commit -m "docs: teach coagent skill permission policies"
```

### Task 6: Final Verification

**Files:**
- Verify all modified files.

- [ ] **Step 1: Run full test suite**

Run:

```bash
.venv/bin/pytest
```

Expected: all tests pass.

- [ ] **Step 2: Inspect final diff**

Run:

```bash
git status --short
git log --oneline -6
```

Expected: only unrelated pre-existing working tree changes remain unstaged, and the recent commits correspond to the permission policy implementation.

- [ ] **Step 3: Manual command sanity check**

Run:

```bash
python -m aisbox.cli run --help
```

Expected: help output includes `--permission-policy` with `default`, `auto`, and `bypass` behavior described.
