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
    assert agent.run_command == ["claude", "-p"]
    assert agent.attach_command == ["claude"]
    assert "npm install -g @anthropic-ai/claude-code" in agent.dockerfile


def test_get_agent_returns_codex_definition():
    agent = get_agent("codex")

    assert agent.name == "codex"
    assert agent.image == "aisbox/codex:latest"
    assert agent.config_path == "/home/aisbox/.codex"
    assert agent.run_command == ["codex", "exec"]
    assert agent.attach_command == ["codex"]
    assert "npm install -g @openai/codex" in agent.dockerfile


@pytest.mark.parametrize("agent_name", ["claude", "codex"])
def test_agent_dockerfile_installs_global_npm_package_before_switching_user(agent_name):
    dockerfile = get_agent(agent_name).dockerfile

    assert dockerfile.index("RUN npm install -g") < dockerfile.index("USER aisbox")
    assert dockerfile.index("USER aisbox") < dockerfile.index("WORKDIR /workspace")


def test_get_agent_rejects_unknown_agent():
    with pytest.raises(AisboxError):
        get_agent("unknown")
