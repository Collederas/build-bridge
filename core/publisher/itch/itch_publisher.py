from pathlib import Path
from core.publisher.base_publisher import BasePublisher
from database import SessionFactory, session_scope
from exceptions import InvalidConfigurationError
from models import ItchConfig, ItchPublishProfile
from views.dialogs.store_upload_dialog import GenericUploadDialog
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
        self.session = SessionFactory()
        self.publish_profile = self._load_profile()

    def _load_profile(self) -> ItchPublishProfile:
        """Loads the Itch.io configuration from the database."""
        # Ensure the config is attached to the session if loaded
        publish_profile = self.session.query(ItchPublishProfile).first()
        if not publish_profile:
            self.session.close()  # Close session if config loading fails early
            raise InvalidConfigurationError(
                "Itch.io configuration not found in settings."
            )
        if not publish_profile.itch_user_game_id:
            self.session.close()
            raise InvalidConfigurationError("Itch.io User/Game ID is not configured.")
        # Ensure object is associated with the session if it came from elsewhere
        if publish_profile not in self.session:
            self.session.add(publish_profile)

        return publish_profile

    def publish(self, content_dir: str, build_id: str, channel_name: str = None):
        """
        Prepares the butler command and launches the ItchUploadDialog to execute it.

        Args:
            content_dir: Path to the directory containing the built game files.
            build_id: The version or identifier for this build (e.g., "1.0.0").
            channel_name: The Itch.io channel name (e.g., "windows-beta", "linux").
        """
        print(f"Preparing Itch.io publish for build: {build_id}")

        if not self.publish_profile:
            raise InvalidConfigurationError("Itch.io publish profile not loaded.")

        # --- Determine Butler Executable ---
        butler_exe = self.publish_profile.itch_config.butler_path or "butler"

        api_key = self.publish_profile.itch_config.api_key
        if not api_key:
            # Close session before raising
            self.session.close()
            raise InvalidConfigurationError(
                "Itch.io API Key not found or configured. Please set it in Settings."
            )

        # --- Determine Channel ---
        if not channel_name:
            # Placeholder: Derive channel name (needs better logic based on build target)
            platform = "windows"  # Example: Derive from BuildTarget.target_platform
            channel_name = f"{platform}-{build_id.replace('.', '-')}"
            print(
                f"Warning: No channel specified, using derived default: {channel_name}"
            )

        itch_target = f"{self.publish_profile.itch_user_game_id}:{channel_name}"

        # --- Construct Butler Command Arguments ---
        # Note: command executable is passed separately to QProcess
        arguments = [
            "push",
            str(Path(content_dir).resolve()),  # Ensure absolute path
            itch_target,
            "--userversion",
            build_id,
        ]

        print(f"Command: {butler_exe} {' '.join(arguments)}")
        print(f"Target: {itch_target}")
        
        title = f"Itch Upload: {publish_profile.project.name} - {build_id}"

        # --- Launch Dialog ---
        try:
            dialog = GenericUploadDialog(
                executable=butler_exe,
                environment={"BUTLER_API_KEY": f"{api_key}", "BUTLER_NO_TTY": "1"},
                title=title,
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
        finally:
            self.session.close()
