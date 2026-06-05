from __future__ import annotations

import re

from aienv.errors import AienvError


ENV_NAME_RE = re.compile(r"^[a-zA-Z0-9_.-]+$")
ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_env_name(name: str) -> str:
    if not ENV_NAME_RE.match(name):
        raise AienvError("Environment name must match [a-zA-Z0-9_.-]+")
    return name


def parse_env_assignment(assignment: str) -> tuple[str, str]:
    if "=" not in assignment:
        raise AienvError("Environment variable must be KEY=VALUE")
    key, value = assignment.split("=", 1)
    if not key or not ENV_KEY_RE.match(key):
        raise AienvError("Environment variable key must match [A-Za-z_][A-Za-z0-9_]*")
    return key, value


def validate_mount_alias(alias: str) -> str:
    if not alias or alias.startswith("/") or "/" in alias or ".." in alias:
        raise AienvError("Mount alias must be a relative name under /workspace")
    return validate_env_name(alias)
