
from build_bridge.database import SessionFactory, session_scope
from build_bridge.models import PublishProfile, SteamPublishProfile
from build_bridge.exceptions import InvalidConfigurationError
from build_bridge.core.publisher.base_publisher import BasePublisher
from build_bridge.core.publisher.steam.steam_pipe_configurator import SteamPipeConfigurator
from build_bridge.views.dialogs.store_upload_dialog import GenericUploadDialog

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
    login_ok = "logged in ok" in log_lower
    build_success = "app build successful" in log_lower or "success" in log_lower # Add more indicators
    no_errors = "error" not in log_lower and "failed" not in log_lower # Basic error check

    return exit_code == 0 and login_ok and build_success and no_errors

class SteamPublisher(BasePublisher):

    def validate_publish_profile(self, publish_profile):
        if not publish_profile:
            raise InvalidConfigurationError("No publish profile in db. Abort publish.")
         
        steam_config = publish_profile.steam_config

        if not steam_config:
             raise InvalidConfigurationError("Steam configuration is missing. Create one in Settings.")
        
        if not steam_config.steamcmd_path:
                raise InvalidConfigurationError("SteamCMD not set in Steam Settings.")


    def publish(self, content_dir: str, build_id: str):
        """Start the Steam publishing process."""
        with session_scope() as session:
            # Read all required config within this scope
            publish_profile = session.query(SteamPublishProfile).filter(
                SteamPublishProfile.build_id == build_id
            ).first()
            
            self.validate_publish_profile(publish_profile)

            configurator = SteamPipeConfigurator(publish_profile=publish_profile)

            vdf_path = configurator.create_or_update_vdf_file(content_root=content_dir)

            configurator = SteamPipeConfigurator(publish_profile=publish_profile)

            # Generate or update the VDF file.
            vdf_path = configurator.create_or_update_vdf_file(content_root=content_dir)


            executable = publish_profile.steam_config.steamcmd_path
            arguments = [
                "+login", publish_profile.steam_config.username, publish_profile.steam_config.password or "", # Include password if set
                "+run_app_build", vdf_path,
                "+quit"
            ]

            # --- Prepare Display Info & Title ---
            display_info = {
                "Build ID": build_id,
                "App ID": str(publish_profile.app_id),
                "Target": f"Steam ({publish_profile.steam_config.username})",
            }
            title = f"Steam Upload: {publish_profile.project.name} - {build_id}"


        # Proceed with publishing
        dialog = GenericUploadDialog(
            executable=executable,
            arguments=arguments,
            display_info=display_info,
            title=title,
            success_checker=check_steam_success
        )
        dialog.exec()

        # Clean up the upload process
        dialog.cleanup()