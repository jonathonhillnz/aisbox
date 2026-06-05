import pytest

from aienv.agents import get_agent, supported_agents
from aienv.errors import AienvError


def test_supported_agents_include_claude_and_codex():
    assert supported_agents() == ["claude", "codex"]


def test_get_agent_returns_claude_definition():
    agent = get_agent("claude")

    assert agent.name == "claude"
    assert agent.image == "aienv/claude:latest"
    assert agent.config_path == "/home/aienv/.claude"
    assert "npm install -g @anthropic-ai/claude-code" in agent.dockerfile


def test_get_agent_rejects_unknown_agent():
    with pytest.raises(AienvError):
        get_agent("unknown")
