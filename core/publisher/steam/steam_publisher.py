
from database import SessionFactory, session_scope
from models import SteamPublishProfile
from exceptions import InvalidConfigurationError
from core.publisher.base_publisher import BasePublisher
from core.publisher.steam.steam_pipe_configurator import SteamPipeConfigurator
from views.dialogs.store_upload_dialog import GenericUploadDialog

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
    def __init__(self):
        super().__init__()

    def publish(self, content_dir: str, build_id: str):
        """Start the Steam publishing process."""
        with session_scope() as session:
            # Read all required config within this scope
            publish_profile = session.query(SteamPublishProfile).filter(
                SteamPublishProfile.build_id == build_id
            ).first()

            if not publish_profile:
                raise InvalidConfigurationError(
                    f"Cannot find publish profile for build: {build_id}"
                )

            configurator = SteamPipeConfigurator(publish_profile=publish_profile)

            # Generate or update the VDF file.
            vdf_path = configurator.create_or_update_vdf_file(content_root=content_dir)

            steam_config = publish_profile.steam_config

            executable = steam_config.steamcmd_path
            arguments = [
                "+login", steam_config.username, steam_config.password or "", # Include password if set
                "+run_app_build", vdf_path,
                "+quit"
            ]

            # --- Prepare Display Info & Title ---
            display_info = {
                "Build ID": build_id,
                "App ID": str(publish_profile.app_id),
                "Target": f"Steam ({steam_config.username})",
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