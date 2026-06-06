from __future__ import annotations

from aisbox.errors import AisboxError
from aisbox.models import AgentDefinition


BASE_DOCKERFILE_PREFIX = """FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       bash ca-certificates curl git nodejs npm \
    && rm -rf /var/lib/apt/lists/*
ARG AISBOX_UID=1000
ARG AISBOX_GID=1000
RUN existing_group="$(getent group "$AISBOX_GID" | cut -d: -f1)" \
    && if [ -n "$existing_group" ] && [ "$existing_group" != "aisbox" ]; then groupmod -n aisbox "$existing_group"; fi \
    && if [ -z "$existing_group" ]; then groupadd -g "$AISBOX_GID" aisbox; fi \
    && existing_user="$(getent passwd "$AISBOX_UID" | cut -d: -f1)" \
    && if [ -n "$existing_user" ] && [ "$existing_user" != "aisbox" ]; then usermod -l aisbox -d /home/aisbox -m "$existing_user"; fi \
    && if [ -z "$existing_user" ]; then useradd -m -u "$AISBOX_UID" -g "$AISBOX_GID" -s /bin/bash aisbox; fi \
    && usermod -g "$AISBOX_GID" -s /bin/bash aisbox
"""


AGENTS = {
    "claude": AgentDefinition(
        name="claude",
        image="aisbox/claude:latest",
        config_path="/home/aisbox",
        dockerfile=BASE_DOCKERFILE_PREFIX
        + "RUN npm install -g @anthropic-ai/claude-code\n"
        + "USER aisbox\n"
        + "WORKDIR /workspace\n",
        run_command=["claude", "-p"],
        attach_command=["claude"],
    ),
    "codex": AgentDefinition(
        name="codex",
        image="aisbox/codex:latest",
        config_path="/home/aisbox",
        dockerfile=BASE_DOCKERFILE_PREFIX
        + "RUN npm install -g @openai/codex\n"
        + "USER aisbox\n"
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
        raise AisboxError(f"Unsupported agent: {name}") from exc
