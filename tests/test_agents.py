import pytest

from aisbox.agents import get_agent, supported_agents
from aisbox.errors import AisboxError


def _apt_install_packages(dockerfile):
    logical_lines = []
    current_line = ""

    for raw_line in dockerfile.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        continues = line.endswith("\\")
        line = line.removesuffix("\\").strip()
        current_line = f"{current_line} {line}".strip()

        if not continues:
            logical_lines.append(current_line)
            current_line = ""

    if current_line:
        logical_lines.append(current_line)

    packages = []
    for line in logical_lines:
        if "apt-get install -y --no-install-recommends" not in line:
            continue

        tokens = line.split()
        marker_index = tokens.index("--no-install-recommends")
        for token in tokens[marker_index + 1 :]:
            if token in {"&&", ";", "|", "||"}:
                break
            packages.append(token)

    return packages


def test_supported_agents_include_claude_codex_and_opencode():
    assert supported_agents() == ["claude", "codex", "opencode"]


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
        "bypass": ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox"],
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


@pytest.mark.parametrize("agent_name", ["claude", "codex", "opencode"])
def test_agent_dockerfile_installs_global_npm_package_before_switching_user(agent_name):
    dockerfile = get_agent(agent_name).dockerfile

    assert dockerfile.index("RUN npm install -g") < dockerfile.index("USER aisbox")
    assert dockerfile.index("USER aisbox") < dockerfile.index("WORKDIR /workspace")


@pytest.mark.parametrize("agent_name", supported_agents())
def test_agent_dockerfile_installs_github_workflow_tools(agent_name):
    dockerfile = get_agent(agent_name).dockerfile
    packages = _apt_install_packages(dockerfile)

    assert "openssh-client" in packages
    assert "gh" in packages
    assert "nano" in packages
    assert "vim" in packages
    assert "git-lfs" not in packages


@pytest.mark.parametrize("agent_name", supported_agents())
def test_agent_dockerfile_uses_official_github_cli_apt_repository(agent_name):
    dockerfile = get_agent(agent_name).dockerfile

    assert "https://cli.github.com/packages/githubcli-archive-keyring.gpg" in dockerfile
    assert "/etc/apt/keyrings/githubcli-archive-keyring.gpg" in dockerfile
    assert (
        "signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] "
        "https://cli.github.com/packages stable main"
        in dockerfile
    )


def test_get_agent_rejects_unknown_agent():
    with pytest.raises(AisboxError):
        get_agent("unknown")
