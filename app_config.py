import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import keyring


class ConfigManager:
    # Dictionary to store singleton instances for each config file
    _instances = {}
    
    def __new__(cls, config_name: str, config_file: Optional[str] = None):
        # Create a separate singleton for each config name
        if config_name not in cls._instances:
            instance = super(ConfigManager, cls).__new__(cls)
            instance._initialized = False
            cls._instances[config_name] = instance
        return cls._instances[config_name]
    
    def __init__(self, config_name: str, config_file: Optional[str] = None):
        if self._initialized:
            return
            
        self.config_name = config_name
        
        # Default config location based on config_name
        if config_file is None:
            app_name = "build_bridge"
            if os.name == "nt":  # Windows
                config_dir = Path(os.getenv("APPDATA")) / app_name
            else:  # macOS/Linux
                config_dir = Path.home() / f".{app_name}"
            
            config_dir.mkdir(exist_ok=True, parents=True)
            self.config_file = config_dir / f"{config_name}.json"
        else:
            self.config_file = Path(config_file)
        
        self.config = {}
        self._initialized = True
        self.load()
    
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration values based on config_name."""
        if self.config_name == "vcs":
            return {
                "provider": "git", 
                "common": {
                    "root_path": "",
                    "project_name": "",
                },
                "git": {
                    "remote_url": "",
                    "username": "",
                    "branch": "main",
                    "ssh_key_path": "",
                    "auto_lfs": True,
                },
                "perforce": {
                    "p4port": "",  # P4 server address (e.g., "perforce:1666")
                    "p4user": "",
                    "p4client": "",  # P4 workspace/client name
                    "stream_path": "",  # P4 stream path (e.g., "//depot/project/main")
                }
            }
        elif self.config_name == "build":
            return {
                "platform": "Win64",
                "configuration": "Development",
                "clean_build": False,
                "build_options": [],
                "unreal": {
                    "engine_path": "C:/Program Files/Epic Games",
                    "archive_directory": "C:/Builds",
                    "build_type": "Development",
                    "target_platforms": ["Win64"],
                    "target_config": "Development",
                    "cook_all": True,
                    "cook_dirs": [],
                    "build_uat_options": [
                        "-map=",
                        "-clientconfig=Development",
                        "-noP4",
                        "-stage",
                        "-archive",
                        "-archivedirectory="
                    ],
                }
            }
        elif self.config_name == "stores":
            return {
                "steam": {
                    "enabled": False,
                    "app_id": "",
                    "depot_id": "",
                    "build_id": "",
                    "builder_path": ""
                }
            }
        else:
            return {}  # Generic empty config for unknown types
        
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key with optional default."""
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value by key."""
        keys = key.split('.')
        config = self.config
        
        # Navigate to the correct nested dict
        for k in keys[:-1]:
            if k not in config or not isinstance(config[k], dict):
                config[k] = {}
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value

    def get_secure(self, service_name, username):
        """Get a securely stored password from the system keyring."""
        try:
            return keyring.get_password(service_name, username)
        except Exception as e:
            print(f"Error retrieving from keyring: {e}")
            return None
            
    def set_secure(self, service_name, username, password):
        """Store a password securely in the system keyring."""
        try:
            keyring.set_password(service_name, username, password)
            return True
        except Exception as e:
            print(f"Error storing in keyring: {e}")
            return False

    def load(self) -> bool:
        """Load configuration from JSON file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, "r") as f:
                    self.config = json.load(f)
                return True
            else:
                # Create default config
                self.config = self._get_default_config()
                self.save()
                return False
        except Exception as e:
            print(f"Error loading config: {e}")
            self.config = self._get_default_config()
            return False 
        
    def save(self) -> bool:
        """Save current configuration to JSON file."""
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.config, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False