import os
from pathlib import Path

from dialogs.steam_upload_dialog import SteamUploadDialog
from exceptions import InvalidConfigurationError
from publisher.base_publisher import BasePublisher
from publisher.steam.steam_wizard import SteamBuildSetupWizard
from conf.config_manager import ConfigManager
from publisher.steam.steam_pipe_configurator import SteamPipeConfigurator


class SteamPublisher(BasePublisher):
    KEYRING_SERVICE = "BuildBridgeSteam"

    def __init__(self):
        # Use ConfigManager for stores
        self.config_manager = ConfigManager("stores")

        # Get basic config data
        self.app_id = self.config_manager.get("steam.app_id", "")
        self.username = self.config_manager.get("steam.username", "")

        # Load password from keyring if username is available
        self.password = ""
        if self.username:
            self.password = (
                self.config_manager.get_secure(self.KEYRING_SERVICE, self.username)
                or ""
            )

        # Load other config values
        self.builder_path = (
            Path(self.config_manager.get("steam.builder_path", "")) / "Steam"
        )
        self.depots = self.config_manager.get("steam.depots", [])

        self.config = {
            "app_id": self.app_id,
            "username": self.username,
            "password": self.password,
            "depots": self.depots,
            "builder_path": self.builder_path,
        }

    def publish(self, build_root: str):
        """Start the Steam publishing process."""
        configurator = SteamPipeConfigurator()

        try:
            # Generate or update the VDF file. 
            configurator.create_or_update_vdf_file(content_root=build_root)

            # Proceed with publishing
            dialog = SteamUploadDialog(
                builder_path=self.builder_path, 
                steam_username=self.username,
                steamcmd_path=self.config_manager.get('steam.steamcmd_path')
            )
            return dialog.exec()

        except Exception as e:
            raise InvalidConfigurationError(
                f"Publishing configuration is incomplete: {e}"
            )

    def save_credentials(self, username, password):
        """Save username and password to the config and keyring"""
        # Save username to config
        self.config_manager.set("steam.username", username)

        # Save password to keyring
        self.config_manager.set_secure(self.KEYRING_SERVICE, username, password)

        # Save config to disk
        self.config_manager.save()

        # Update local variables
        self.username = username
        self.password = password
        self.config["username"] = username
        self.config["password"] = password
