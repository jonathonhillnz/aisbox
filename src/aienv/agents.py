from __future__ import annotations

from aienv.errors import AienvError
from aienv.models import AgentDefinition


BASE_DOCKERFILE_PREFIX = """FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       bash ca-certificates curl git nodejs npm \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m -s /bin/bash aienv
"""


AGENTS = {
    "claude": AgentDefinition(
        name="claude",
        image="aienv/claude:latest",
        config_path="/home/aienv/.claude",
        dockerfile=BASE_DOCKERFILE_PREFIX
        + "RUN npm install -g @anthropic-ai/claude-code\n"
        + "USER aienv\n"
        + "WORKDIR /workspace\n",
        run_command=["claude", "-p"],
        attach_command=["claude"],
    ),
    "codex": AgentDefinition(
        name="codex",
        image="aienv/codex:latest",
        config_path="/home/aienv/.codex",
        dockerfile=BASE_DOCKERFILE_PREFIX
        + "RUN npm install -g @openai/codex\n"
        + "USER aienv\n"
        + "WORKDIR /workspace\n",
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
        raise AienvError(f"Unsupported agent: {name}") from exc
