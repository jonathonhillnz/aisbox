from __future__ import annotations

import re

from aisbox.errors import AisboxError


ENV_NAME_RE = re.compile(r"^[a-zA-Z0-9_.-]+$")
ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_env_name(name: str) -> str:
    if name in {".", ".."} or not ENV_NAME_RE.match(name):
        raise AisboxError("Environment name must match [a-zA-Z0-9_.-]+")
    return name


def parse_env_assignment(assignment: str) -> tuple[str, str]:
    if "=" not in assignment:
        raise AisboxError("Environment variable must be KEY=VALUE")
    key, value = assignment.split("=", 1)
    if not key or not ENV_KEY_RE.match(key):
        raise AisboxError("Environment variable key must match [A-Za-z_][A-Za-z0-9_]*")
    return key, value


def validate_mount_alias(alias: str) -> str:
    if not alias or alias.startswith("/") or "/" in alias or ".." in alias:
        raise AisboxError("Mount alias must be a relative name under /workspace")
    return validate_env_name(alias)
