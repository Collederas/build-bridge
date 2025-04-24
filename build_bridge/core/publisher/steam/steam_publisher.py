from build_bridge.database import session_scope
from build_bridge.models import SteamPublishProfile
from build_bridge.exceptions import InvalidConfigurationError
from build_bridge.core.publisher.base_publisher import BasePublisher
from build_bridge.core.publisher.steam.steam_pipe_configurator import (
    SteamPipeConfigurator,
)
from build_bridge.views.dialogs.publish_dialog import GenericUploadDialog

def check_steam_success(exit_code: int, log_content: str) -> bool:
    """
    Checks steamcmd output for success indicators.

    Args:
        exit_code: The exit code from the QProcess.
        log_content: The accumulated stdout/stderr from the process.

    Returns:
        True if the upload seems successful, False otherwise.
    """
    log_lower = log_content.lower()

    # Check for successful login
    login_ok = "to steam public...ok" in log_lower

    # Check for successful build
    build_success = (
        "app build successful" in log_lower or 
        "successfully finished" in log_lower
    )

    # Check for absence of actual errors (exclude benign cases like 'stderr')
    no_errors = not (
        "error" in log_lower.replace("stderr", "") or 
        "failed" in log_lower
    )

    return exit_code == 0 and login_ok and build_success and no_errors


class SteamPublisher(BasePublisher):

    def __init__(self, publish_profile: SteamPublishProfile,  publish_playtest=False):
        self.publish_profile = publish_profile
        self.publish_playtest = publish_playtest

    def validate_publish_profile(self):
        """Raises InvalidCoinfigurtionError on any fail"""        
        if not self.publish_profile:
            raise InvalidConfigurationError("No publish profile in db.")

        steam_config = self.publish_profile.steam_config

        if not steam_config:
            raise InvalidConfigurationError(
                "Steam configuration is missing. Create one in Settings."
            )

        if not steam_config.steamcmd_path:
            raise InvalidConfigurationError("SteamCMD not set in Steam Settings.")

    def publish(self, content_dir):
        """Start the Steam publishing process."""

        self.validate_publish_profile()

        configurator = SteamPipeConfigurator(publish_profile=self.publish_profile, publish_playtest=self.publish_playtest)

        vdf_path = configurator.create_or_update_vdf_file(content_root=content_dir)

        # Generate or update the VDF file.
        executable = self.publish_profile.steam_config.steamcmd_path
        arguments = [
            "+login",
            self.publish_profile.steam_config.username,
            self.publish_profile.steam_config.password or "",  # Include password if set
            "+run_app_build",
            vdf_path,
            "+quit",
        ]

        # --- Prepare Display Info & Title ---
        display_info = {
            "Build ID": self.publish_profile.build_id,
            "App ID": str(self.publish_profile.app_id),
            "Target": f"Steam ({self.publish_profile.steam_config.username})",
        }
        title = f"Steam Upload: {self.publish_profile.project.name} - {self.publish_profile.build_id}"

        # Proceed with publishing
        dialog = GenericUploadDialog(
            executable=executable,
            arguments=arguments,
            display_info=display_info,
            title=title,
            success_checker=check_steam_success,
        )
        dialog.exec()

        # Clean up the upload process
        dialog.cleanup()
