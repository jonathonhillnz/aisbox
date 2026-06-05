from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict
from pathlib import Path

from aisbox.errors import AisboxError
from aisbox.models import Environment, Mount
from aisbox.validation import parse_env_assignment, validate_env_name, validate_mount_alias


class EnvironmentStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or os.environ.get("AISBOX_HOME", "~/.aisbox")).expanduser()

    def env_dir(self, name: str) -> Path:
        return self.root / validate_env_name(name)

    def config_dir(self, name: str) -> Path:
        return self.env_dir(name) / "config"

    def default_workspace(self, name: str) -> Path:
        return self.env_dir(name) / "files"

    def exists(self, name: str) -> bool:
        return (self.env_dir(name) / "environment.json").exists()

    def create_dirs(self, name: str, agent: str) -> None:
        validate_env_name(agent)
        self.config_dir(name).mkdir(parents=True, exist_ok=True)
        self.default_workspace(name).mkdir(parents=True, exist_ok=True)

    def save(self, env: Environment) -> None:
        env_dir = self.env_dir(env.name)
        env_dir.mkdir(parents=True, exist_ok=True)
        payload = asdict(env)
        (env_dir / "environment.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def load(self, name: str) -> Environment:
        path = self.env_dir(name) / "environment.json"
        if not path.exists():
            raise AisboxError(f"Environment does not exist: {name}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["name"] = validate_env_name(payload["name"])
        payload["agent"] = validate_env_name(payload["agent"])
        payload["env"] = {
            parse_env_assignment(f"{key}=ignored")[0]: value
            for key, value in payload.get("env", {}).items()
        }
        payload["mounts"] = [
            Mount(source=str(mount["source"]), alias=validate_mount_alias(mount["alias"]))
            for mount in payload.get("mounts", [])
        ]
        return Environment(**payload)

    def list(self) -> list[Environment]:
        if not self.root.exists():
            return []
        envs = []
        for path in self.root.iterdir():
            state_file = path / "environment.json"
            if state_file.exists():
                envs.append(self.load(path.name))
        return sorted(envs, key=lambda env: env.name)

    def delete(self, name: str) -> None:
        if not self.exists(name):
            raise AisboxError(f"Environment does not exist: {name}")
        shutil.rmtree(self.env_dir(name))
