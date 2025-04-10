from pathlib import Path
from build_bridge.core.publisher.base_publisher import BasePublisher
from build_bridge.database import session_scope
from build_bridge.exceptions import InvalidConfigurationError
from build_bridge.models import ItchPublishProfile, StoreEnum
from build_bridge.views.dialogs.store_upload_dialog import GenericUploadDialog
from PyQt6.QtWidgets import QDialog


def check_itch_success(exit_code: int, log_content: str) -> bool:
    """
    Checks butler output for success indicators.

    Args:
        exit_code: The exit code from the QProcess.
        log_content: The accumulated stdout/stderr from the process.

    Returns:
        True if the upload seems successful, False otherwise.
    """
    log_lower = log_content.lower()
    success_indicators = ["build is processed", "patch applied", "tasks ended."]
    error_indicators = ["error:", "failed", "panic:", "invalid api key", "denied"]

    is_success = (
        exit_code == 0
        and any(ind in log_lower for ind in success_indicators)
        and not any(err in log_lower for err in error_indicators)
    )

    return is_success


class ItchPublisher(BasePublisher):
    def __init__(self):
        self.publish_profile = self._load_profile()

    def _load_profile(self) -> ItchPublishProfile:
        """Loads the Itch.io configuration from the database."""
        # Ensure the config is attached to the session if loaded
        with session_scope() as session:
            publish_profile = session.query(ItchPublishProfile).filter_by(store_type=StoreEnum.itch).first()
            self.validate_publish_profile(publish_profile)
            
            api_key = publish_profile.itch_config.api_key

            butler_exe = publish_profile.itch_config.butler_path or "butler"

            platform = "windows"  # Example: Derive from BuildTarget.target_platform
            channel_name = publish_profile.itch_channel_name

            itch_target = f"{publish_profile.itch_user_game_id}:{channel_name}"
            project_name = publish_profile.project.name

            publish_profile = dict(
                butler_exe=butler_exe,
                api_key=api_key,
                platform=platform,
                channel=channel_name,
                itch_target=itch_target,
                project_name=project_name,
            )

            return publish_profile
        
    def validate_publish_profile(self, publish_profile):
        """Ensures config is valid alnd allows publishing"""
        if not publish_profile:
            raise InvalidConfigurationError(f"Itch.io Publish Profile not found.")

        if not publish_profile.itch_user_game_id:
            raise InvalidConfigurationError(
                "Itch.io User/Game ID is not configured."
            )
        
        if not publish_profile:
            raise InvalidConfigurationError("Itch.io publish profile not loaded.")
        
        if not publish_profile.itch_config.api_key:
            raise InvalidConfigurationError(
                "Itch.io API Key not found or configured. Please set it in Settings."
            )
        
        if not publish_profile.itch_config.butler_path:
            raise InvalidConfigurationError(
                "Butler not found. Please set it in Settings."
            )       

    def publish(self, content_dir: str, build_id: str):
        """
        Prepares the butler command and launches the ItchUploadDialog to execute it.

        Args:
            content_dir: Path to the directory containing the built game files.
            build_id: The version or identifier for this build (e.g., "1.0.0").
            channel_name: The Itch.io channel name (e.g., "windows-beta", "linux").
        """
        print(f"Preparing Itch.io publish for build: {build_id}")

        # --- Construct Butler Command Arguments ---
        # Note: command executable is passed separately to QProcess
        itch_target = self.publish_profile.get("itch_target")
        butler_exe = self.publish_profile.get("butler_exe")

        arguments = [
            "push",
            str(Path(content_dir).resolve()),  # Ensure absolute path
            itch_target,
            "--userversion",
            build_id,
        ]

        print(f"Command: {butler_exe} {' '.join(arguments)}")
        print(f"Target: {itch_target}")
        # --- Launch Dialog ---
        try:
            dialog = GenericUploadDialog(
                executable=butler_exe,
                environment={
                    "BUTLER_API_KEY": f"{self.publish_profile.get('api_key')}",
                    "BUTLER_NO_TTY": "1",
                },
                title=self.publish_profile.get("title"),
                arguments=arguments,
                display_info={  # Pass info for display in the dialog
                    "build_id": build_id,
                    "target": itch_target,
                    "content_dir": content_dir,
                },
                success_checker=check_itch_success,
            )
            # The dialog will handle QProcess execution and feedback
            result = dialog.exec()

            if result == QDialog.DialogCode.Rejected:
                # Check if rejection was due to failure or cancellation
                # The dialog itself should log the specific reason
                print(
                    "Itch.io upload dialog closed with Rejected status (failed or cancelled)."
                )
            else:
                print(
                    "Itch.io upload dialog closed with Accepted status (likely successful)."
                )

        except FileNotFoundError:
            # This might occur if butler_exe path is wrong before QProcess tries
            raise InvalidConfigurationError(
                f"Butler executable not found at '{butler_exe}'."
            )
        except Exception as e:
            print(f"An error occurred launching or running the Itch upload dialog: {e}")
            raise
