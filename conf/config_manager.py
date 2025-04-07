import json
import os
from pathlib import Path
from typing import Any, Optional

import keyring


class ConfigManager:
    _instances = {}

    def __new__(cls, config_name: str, config_file: Optional[str] = None):
        if config_name not in cls._instances:
            instance = super(ConfigManager, cls).__new__(cls)
            instance._initialized = False
            cls._instances[config_name] = instance
        return cls._instances[config_name]

    def __init__(self, config_name: str, config_file: Optional[str] = None):
        if self._initialized:
            return
        self.config_name = config_name
        if config_file is None:
            app_name = "build_bridge"
            config_dir = Path(os.getenv("APPDATA") if os.name == "nt" else Path.home() / f".{app_name}")
            config_dir.mkdir(exist_ok=True, parents=True)
            self.config_file = config_dir / f"{config_name}.json"
        else:
            self.config_file = Path(config_file)
        self._initialized = True

    def load(self, model_class) -> Any:
        """Load config into a model instance."""
        try:
            if self.config_file.exists():
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                return model_class(data)
            else:
                instance = model_class()
                self.save(instance)
                return instance
        except Exception as e:
            print(f"Error loading config: {e}")
            return model_class()

    def save(self, model_instance) -> bool:
        """Save a model instance to file."""
        try:
            with open(self.config_file, "w") as f:
                json.dump(model_instance.to_dict(), f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the model instance by dotted key."""
        keys = key.split('.')
        value = model_instance.to_dict()
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        """Set a value in the model instance by dotted key."""
        keys = key.split('.')
        config = model_instance.data
        for k in keys[:-1]:
            if k not in config or not isinstance(config[k], dict):
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value

    def get_secure(self, service_name: str, username: str) -> Optional[str]:
        try:
            return keyring.get_password(service_name, username)
        except Exception as e:
            print(f"Error retrieving from keyring: {e}")
            return None

    def set_secure(self, service_name: str, username: str, password: str) -> bool:
        try:
            keyring.set_password(service_name, username, password)
            return True
        except Exception as e:
            print(f"Error storing in keyring: {e}")
            return False