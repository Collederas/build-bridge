import os
from pathlib import Path

from database import SessionFactory
from models import SteamBuildPublishProfile
from views.dialogs.steam_upload_dialog import SteamUploadDialog
from exceptions import InvalidConfigurationError
from core.publisher.base_publisher import BasePublisher
from core.publisher.steam.steam_pipe_configurator import SteamPipeConfigurator


class SteamPublisher(BasePublisher):
    KEYRING_SERVICE = "BuildBridgeSteam"

    def __init__(self):
        # Use ConfigManager for stores
        self.session = SessionFactory()

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

    def publish(self, content_dir: str, build_id: str):
        """Start the Steam publishing process."""
        
        self.publish_profile = self.session.query(SteamBuildPublishProfile).filter(
            SteamBuildPublishProfile.build_id == build_id
        )

        if not self.publish_profile:
            raise InvalidConfigurationError(
                f"Cannot find publish profile for build: {build_id}"
            )

        configurator = SteamPipeConfigurator()

        try:
            # Generate or update the VDF file.
            configurator.create_or_update_vdf_file(content_root=content_dir)

            steamcmd_path = self.config_manager.get("steam.steamcmd_path", "")
            if not os.path.exists(steamcmd_path):
                raise InvalidConfigurationError(
                    "SteamCMD path is invalid. Please check your configuration."
                )

            # Proceed with publishing
            dialog = SteamUploadDialog(
                builder_path=self.builder_path,
                steam_username=self.username,
                steamcmd_path=steamcmd_path,
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
