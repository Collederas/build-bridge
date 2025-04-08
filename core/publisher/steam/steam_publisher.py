import os
from pathlib import Path

from database import SessionFactory
from models import SteamPublishProfile
from views.dialogs.steam_upload_dialog import SteamUploadDialog
from exceptions import InvalidConfigurationError
from core.publisher.base_publisher import BasePublisher
from core.publisher.steam.steam_pipe_configurator import SteamPipeConfigurator


class SteamPublisher(BasePublisher):
    def __init__(self):
        # Use ConfigManager for stores
        self.session = SessionFactory()

    def publish(self, content_dir: str, build_id: str):
        """Start the Steam publishing process."""

        publish_profile = self.session.query(SteamPublishProfile).filter(
            SteamPublishProfile.build_id == build_id
        )

        if not publish_profile:
            raise InvalidConfigurationError(
                f"Cannot find publish profile for build: {build_id}"
            )

        configurator = SteamPipeConfigurator(publish_profile=publish_profile)

        try:
            # Generate or update the VDF file.
            configurator.create_or_update_vdf_file(content_root=content_dir)
            
            steamcmd_path = publish_profile.steamcmd_path

            # Proceed with publishing
            dialog = SteamUploadDialog(
                builder_path=publish_profile.builder_path,
                steam_config=publish_profile.steam_config,
                steamcmd_path=steamcmd_path,
            )
            return dialog.exec()

        except Exception as e:
            raise InvalidConfigurationError(
                f"Publishing configuration is incomplete: {e}"
            )
