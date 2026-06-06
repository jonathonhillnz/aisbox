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

    def settings_path(self) -> Path:
        return self.root / "settings.json"

    def exists(self, name: str) -> bool:
        return (self.env_dir(name) / "environment.json").exists()

    def read_settings(self) -> dict[str, object]:
        path = self.settings_path()
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise AisboxError("Settings file must contain a JSON object")
        return payload

    def write_settings(self, settings: dict[str, object]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.settings_path().write_text(
            json.dumps(settings, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def set_default_environment(self, name: str) -> None:
        name = validate_env_name(name)
        if not self.exists(name):
            raise AisboxError(f"Environment does not exist: {name}")
        settings = self.read_settings()
        settings["default_environment"] = name
        self.write_settings(settings)

    def load_default_environment(self) -> str | None:
        settings = self.read_settings()
        name = settings.get("default_environment")
        if name is None:
            return None
        if not isinstance(name, str):
            raise AisboxError("Default environment setting must be a string")
        name = validate_env_name(name)
        if not self.exists(name):
            raise AisboxError(f"Environment does not exist: {name}")
        return name

    def clear_default_environment(self) -> None:
        settings = self.read_settings()
        if "default_environment" not in settings:
            return
        del settings["default_environment"]
        self.write_settings(settings)

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
        current_default = self.load_default_environment()
        if current_default == validate_env_name(name):
            self.clear_default_environment()
        shutil.rmtree(self.env_dir(name))
