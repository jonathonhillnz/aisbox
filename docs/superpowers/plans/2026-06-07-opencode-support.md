# OpenCode Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add OpenCode as a fully supported aisbox agent with the same build, run, interactive, retained-session, rebuild, doctor, persistence, and documentation behavior as Claude Code and Codex CLI.

**Architecture:** Extend the existing data-only `AGENTS` registry with an OpenCode definition. Reuse the generic Docker command builder, environment store, CLI orchestration, and retained-session lifecycle without adding agent-specific branches. Persist OpenCode's XDG configuration and credential state through the existing `/home/aisbox` bind mount.

**Tech Stack:** Python 3.11+, Typer, pytest, Docker command construction, Ubuntu 24.04 images, npm package `opencode-ai@latest`.

---

## File Structure

- Modify `src/aisbox/agents.py`: define the OpenCode image, install command, and interactive/non-interactive commands.
- Modify `tests/test_agents.py`: verify registry membership, definition fields, and Dockerfile ordering.
- Modify `tests/test_docker.py`: verify OpenCode run, disposable start, and retained start commands.
- Modify `tests/test_cli_core.py`: verify OpenCode environments can be created, listed, and inspected through generic CLI paths.
- Modify `tests/test_cli_runtime.py`: verify rebuild uses the stored OpenCode definition.
- Modify `tests/test_doctor.py`: verify doctor reports all three agents.
- Modify `tests/test_repository_docs.py`: encode OpenCode support, authentication, compatibility, and host-isolation requirements.
- Modify `README.md`: document OpenCode support, commands, authentication, persistence, and limitations.
- Modify `AGENTS.md`: expand the repository safety contract to cover host OpenCode state.

### Task 1: Add And Prove The OpenCode Agent Definition

**Files:**
- Modify: `tests/test_agents.py:7-38`
- Modify: `tests/test_docker.py:101-210`
- Modify: `tests/test_cli_core.py:49-81`
- Modify: `tests/test_cli_runtime.py:656-665`
- Modify: `tests/test_doctor.py:18-35`
- Modify: `src/aisbox/agents.py:25-48`

- [ ] **Step 1: Update agent-definition tests to require OpenCode**

Replace the supported-agent test in `tests/test_agents.py` with:

```python
def test_supported_agents_include_claude_codex_and_opencode():
    assert supported_agents() == ["claude", "codex", "opencode"]
```

Add this definition test after the Codex test:

```python
def test_get_agent_returns_opencode_definition():
    agent = get_agent("opencode")

    assert agent.name == "opencode"
    assert agent.image == "aisbox/opencode:latest"
    assert agent.config_path == "/home/aisbox"
    assert agent.run_command == ["opencode", "run"]
    assert agent.attach_command == ["opencode"]
    assert "npm install -g opencode-ai@latest" in agent.dockerfile
```

Extend the Dockerfile-order parametrization:

```python
@pytest.mark.parametrize("agent_name", ["claude", "codex", "opencode"])
def test_agent_dockerfile_installs_global_npm_package_before_switching_user(agent_name):
    dockerfile = get_agent(agent_name).dockerfile

    assert dockerfile.index("RUN npm install -g") < dockerfile.index("USER aisbox")
    assert dockerfile.index("USER aisbox") < dockerfile.index("WORKDIR /workspace")
```

- [ ] **Step 2: Add Docker command tests for OpenCode**

Add these tests to `tests/test_docker.py` near the existing run/start command tests:

```python
def opencode_environment() -> Environment:
    return Environment(
        name="demo1",
        agent="opencode",
        env={},
        workspace="/tmp/workspace",
        mounts=[],
        image="aisbox/opencode:latest",
        created_at="2026-06-07T00:00:00Z",
    )


def test_container_command_runs_opencode_non_interactively():
    command = container_command(
        opencode_environment(),
        get_agent("opencode"),
        "/tmp/config",
        "run",
        "hello",
    )

    assert "/tmp/config:/home/aisbox" in command
    assert command[-3:] == ["opencode", "run", "hello"]


def test_container_command_starts_opencode_interactively():
    command = container_command(
        opencode_environment(),
        get_agent("opencode"),
        "/tmp/config",
        "start",
    )

    assert "--rm" in command
    assert "-it" in command
    assert command[-1:] == ["opencode"]


def test_container_command_starts_retained_opencode_session():
    command = container_command(
        opencode_environment(),
        get_agent("opencode"),
        "/tmp/config",
        "start",
        retained=True,
    )

    assert "--rm" not in command
    assert f"{AGENT_LABEL}=opencode" in command
    assert command[-1:] == ["opencode"]
```

- [ ] **Step 3: Add CLI and doctor parity tests**

Add this test to `tests/test_cli_core.py` after
`test_create_list_and_inspect_environment`:

```python
def test_create_list_and_inspect_opencode_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    build_mock = Mock()
    monkeypatch.setattr("aisbox.commands.build_image", build_mock)

    created = runner.invoke(
        app,
        ["create", "-n", "demo1", "-a", "opencode"],
    )
    listed = runner.invoke(app, ["list"])
    inspected = runner.invoke(app, ["inspect", "-n", "demo1"])

    assert created.exit_code == 0
    assert listed.stdout.strip().split("\t")[:2] == ["demo1", "opencode"]
    assert "agent: opencode" in inspected.stdout
    assert "image: aisbox/opencode:latest" in inspected.stdout
    assert build_mock.call_args.args[0].name == "opencode"
```

Add the missing import at the top of `tests/test_cli_core.py`:

```python
from unittest.mock import Mock
```

Add this test to `tests/test_cli_runtime.py` after the existing rebuild test:

```python
def test_rebuild_invokes_image_build_for_opencode(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    monkeypatch.setattr("aisbox.commands.build_image", lambda agent: None)
    created = runner.invoke(
        app,
        ["create", "-n", "demo1", "-a", "opencode"],
    )
    assert created.exit_code == 0

    build_mock = Mock()
    monkeypatch.setattr("aisbox.commands.build_image", build_mock)

    result = runner.invoke(app, ["rebuild", "-n", "demo1"])

    assert result.exit_code == 0
    assert build_mock.call_args.args[0].name == "opencode"
```

Update the doctor assertion in `tests/test_doctor.py`:

```python
assert "Supported agents: claude, codex, opencode" in result.stdout
```

- [ ] **Step 4: Run the focused tests and verify they fail**

Run:

```bash
.venv/bin/pytest \
  tests/test_agents.py \
  tests/test_docker.py \
  tests/test_cli_core.py::test_create_list_and_inspect_opencode_environment \
  tests/test_cli_runtime.py::test_rebuild_invokes_image_build_for_opencode \
  tests/test_doctor.py::test_doctor_success_creates_private_state_root_regardless_of_umask \
  -v
```

Expected: failures report that `opencode` is absent from `supported_agents()`
and `get_agent("opencode")` raises `AisboxError`.

- [ ] **Step 5: Add the OpenCode agent definition**

Add this entry after Codex in `src/aisbox/agents.py`:

```python
    "opencode": AgentDefinition(
        name="opencode",
        image="aisbox/opencode:latest",
        config_path="/home/aisbox",
        dockerfile=BASE_DOCKERFILE_PREFIX
        + "RUN npm install -g opencode-ai@latest\n"
        + "USER aisbox\n"
        + "WORKDIR /workspace\n",
        run_command=["opencode", "run"],
        attach_command=["opencode"],
    ),
```

Do not add environment defaults, provider defaults, port publishing, or
OpenCode-specific command branches.

- [ ] **Step 6: Run the focused tests and verify they pass**

Run:

```bash
.venv/bin/pytest \
  tests/test_agents.py \
  tests/test_docker.py \
  tests/test_cli_core.py::test_create_list_and_inspect_opencode_environment \
  tests/test_cli_runtime.py::test_rebuild_invokes_image_build_for_opencode \
  tests/test_doctor.py::test_doctor_success_creates_private_state_root_regardless_of_umask \
  -v
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit the agent support**

```bash
git add \
  src/aisbox/agents.py \
  tests/test_agents.py \
  tests/test_docker.py \
  tests/test_cli_core.py \
  tests/test_cli_runtime.py \
  tests/test_doctor.py
git commit -m "feat: add opencode agent support"
```

### Task 2: Document Authentication, Compatibility, And Host Isolation

**Files:**
- Modify: `tests/test_repository_docs.py:436-477`
- Modify: `tests/test_repository_docs.py:591-640`
- Modify: `tests/test_cli_core.py:278-294`
- Modify: `README.md:1-128`
- Modify: `README.md:217-224`
- Modify: `AGENTS.md:11-19`

- [ ] **Step 1: Update repository documentation tests**

In `test_readme_states_preview_and_safety_contract`, require OpenCode and the
expanded host-state statement:

```python
    for text in [
        "Public preview",
        "Python 3.11",
        "Docker",
        "pipx",
        "AISBOX_HOME",
        "Host `~/.claude`, `~/.codex`, and OpenCode user configuration",
        "does not run Docker through `sudo`",
        "Claude",
        "Codex",
        "OpenCode",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "Apache-2.0",
    ]:
        assert text in readme
```

Add a focused OpenCode documentation test:

```python
def test_readme_documents_opencode_support_and_authentication():
    readme = read_text("README.md")
    supported = readme.split("## Supported Agents", 1)[1].split(
        "## Authentication", 1
    )[0]
    authentication = readme.split("## Authentication", 1)[1].split(
        "## Workspaces And Persistence", 1
    )[0]
    normalized_auth = " ".join(authentication.split())

    for text in [
        "| OpenCode | `opencode` | `opencode run` |",
        "aisbox create -n demo1 -a opencode",
    ]:
        assert text in readme

    assert "OpenCode" in supported
    assert "`/connect`" in normalized_auth
    assert "OpenCode Zen" in normalized_auth
    assert "ANTHROPIC_API_KEY=" in normalized_auth
    assert "OPENAI_API_KEY=" in normalized_auth
    assert "`{env:NAME}`" in normalized_auth
    assert "many providers" in normalized_auth
    assert "OPENCODE_API_KEY=" not in authentication
```

Add a compatibility and isolation test:

```python
def test_readme_documents_opencode_project_compatibility_without_host_access():
    readme = read_text("README.md")
    normalized = " ".join(readme.split())

    assert "project `CLAUDE.md` and `.claude/skills`" in normalized
    assert "mounted workspace" in normalized
    assert "host `~/.claude`" in normalized
    assert "not copied or mounted" in normalized
```

Update `test_agents_guidance_matches_retained_container_safety_contract` to
expect:

```python
"Host `~/.claude`, `~/.codex`, and OpenCode user configuration must not be copied or mounted."
```

Update the README assertion in `tests/test_cli_core.py` to use the same expanded
safety sentence.

- [ ] **Step 2: Run documentation tests and verify they fail**

Run:

```bash
.venv/bin/pytest \
  tests/test_repository_docs.py::test_readme_states_preview_and_safety_contract \
  tests/test_repository_docs.py::test_readme_documents_opencode_support_and_authentication \
  tests/test_repository_docs.py::test_readme_documents_opencode_project_compatibility_without_host_access \
  tests/test_repository_docs.py::test_agents_guidance_matches_retained_container_safety_contract \
  tests/test_cli_core.py::test_readme_documents_primary_commands \
  -v
```

Expected: failures identify missing OpenCode documentation and the old
two-agent host-isolation wording.

- [ ] **Step 3: Update the README overview, safety model, and supported-agent table**

Change the opening sentence to:

```markdown
`aisbox` runs Claude Code, Codex CLI, and OpenCode inside Docker containers.
```

Replace the host-state safety bullet with:

```markdown
- Host `~/.claude`, `~/.codex`, and OpenCode user configuration and credential
  directories are not copied or mounted.
```

Add an OpenCode quick-start example:

````markdown
Create an OpenCode environment:

```bash
aisbox create -n demo1 -a opencode --workspace /path/to/source
```
````

Add OpenCode to the supported-agent table:

```markdown
| OpenCode | `opencode` | `opencode run` |
```

- [ ] **Step 4: Update README authentication and compatibility guidance**

Keep the existing generic hidden-prompt explanation, but expand the
authentication section with:

````markdown
For OpenCode, start the TUI and run `/connect`:

```bash
aisbox start -n demo1
```

Use `/connect` to configure OpenCode Zen or another supported provider.
OpenCode also recognizes provider credentials supplied through the environment;
for example:

```bash
aisbox create -n demo1 -a opencode -e ANTHROPIC_API_KEY=
aisbox env set -n demo1 -e OPENAI_API_KEY=
```

OpenCode supports many providers. Its `opencode.json` configuration can
reference any environment variable supplied to the container using
`{env:NAME}`. Consult the OpenCode provider documentation for provider-specific
requirements.
````

In `Workspaces And Persistence`, add:

```markdown
OpenCode may read project `CLAUDE.md` and `.claude/skills` files from the
mounted workspace through its upstream compatibility behavior. aisbox does not
copy or mount host `~/.claude` state.
```

Replace the preview limitation:

```markdown
- Only Claude Code, Codex CLI, and OpenCode are supported.
```

Do not document `OPENCODE_API_KEY` as the OpenCode Zen setup mechanism. Do not
add exhaustive OpenCode runtime or experimental environment-variable lists.

- [ ] **Step 5: Update the repository safety contract**

Replace the host-state bullet in `AGENTS.md` with:

```markdown
- Host `~/.claude`, `~/.codex`, and OpenCode user configuration must not be
  copied or mounted.
```

- [ ] **Step 6: Run documentation tests and verify they pass**

Run:

```bash
.venv/bin/pytest \
  tests/test_repository_docs.py \
  tests/test_cli_core.py::test_readme_documents_primary_commands \
  -v
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit the documentation and safety contract**

```bash
git add README.md AGENTS.md tests/test_repository_docs.py tests/test_cli_core.py
git commit -m "docs: explain opencode support"
```

### Task 3: Verify The Complete Change

**Files:**
- Verify: `src/aisbox/agents.py`
- Verify: `tests/`
- Verify: `README.md`
- Verify: `AGENTS.md`

- [ ] **Step 1: Run formatting and whitespace checks**

Run:

```bash
git diff --check HEAD~2
```

Expected: no output.

- [ ] **Step 2: Run the complete test suite**

Run:

```bash
.venv/bin/pytest
```

Expected: all tests pass.

- [ ] **Step 3: Check the CLI reports OpenCode**

Run:

```bash
AISBOX_HOME="$(mktemp -d)" .venv/bin/python -m aisbox.cli doctor
```

Expected output includes:

```text
Supported agents: claude, codex, opencode
```

The command may exit non-zero if Docker is unavailable, but it must still list
all three supported agents and must not emit a traceback.

- [ ] **Step 4: Review the final diff for scope**

Run:

```bash
git status --short
git diff HEAD~2 --stat
git diff HEAD~2 -- src/aisbox/agents.py README.md AGENTS.md
```

Expected:

- only the planned source, test, and documentation files changed
- no generated `build/` files changed
- no host credential paths were added as mounts
- no OpenCode-specific command branches, port publishing, or environment
  defaults were introduced

## Plan Self-Review

- **Spec coverage:** Tasks 1 and 2 cover the agent definition, npm install,
  run/start commands, full generic CLI parity, home persistence, authentication,
  OpenCode Zen guidance, provider environment examples, Claude compatibility,
  host isolation, doctor output, tests, and documentation.
- **Scope:** The production change remains one agent registry entry. Tests prove
  that existing generic orchestration supplies the required parity.
- **Type consistency:** The plan uses the existing `AgentDefinition` fields
  `name`, `image`, `config_path`, `dockerfile`, `run_command`, and
  `attach_command` without changing their signatures.
- **No placeholders:** Every implementation and verification step includes
  exact code or commands and an expected result.
