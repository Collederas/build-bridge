import logging
from pathlib import Path

from build_bridge.core.publisher.base_publisher import BasePublisher
from build_bridge.exceptions import InvalidConfigurationError
from build_bridge.models import PublishProfile
from build_bridge.views.dialogs.publish_dialog import GenericUploadDialog
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
    def __init__(self, publish_profile: PublishProfile):
        self.publish_profile = publish_profile

    def validate_publish_profile(self):
        """Ensures config is valid alnd allows publishing"""
        if not self.publish_profile:
            raise InvalidConfigurationError(f"Itch.io Publish Profile not found.")

        if not self.publish_profile.itch_user_game_id:
            raise InvalidConfigurationError("Itch.io User/Game ID is not configured.")

        if not self.publish_profile:
            raise InvalidConfigurationError("Itch.io publish profile not loaded.")

        if not self.publish_profile.itch_config.api_key:
            raise InvalidConfigurationError(
                "Itch.io API Key not found or configured. Please set it in Settings."
            )

        if not self.publish_profile.itch_config.butler_path:
            raise InvalidConfigurationError(
                "Butler not found. Please set it in Settings."
            )

    def publish(self, content_dir: str):
        """
        Prepares the butler command and launches the ItchUploadDialog to execute it.

        Args:
            content_dir: Path to the directory containing the built game files.
            build_id: The version or identifier for this build (e.g., "1.0.0").
        """
        logging.info(f"Preparing Itch.io publish for build: {self.publish_profile.build_id}")

        # --- Construct Butler Command Arguments ---
        # Note: command executable is passed separately to QProcess
        itch_target = self.publish_profile.itch_user_game_id
        butler_exe = self.publish_profile.itch_config.butler_path

        arguments = [
            "push",
            str(Path(content_dir).resolve()),  # Ensure absolute path
            f"{itch_target}:{self.publish_profile.itch_channel_name}",
            "--userversion",
            self.publish_profile.build_id,
        ]

        logging.info(f"Command: {butler_exe} {' '.join(arguments)}")
        logging.info(f"Target: {itch_target}")
        # --- Launch Dialog ---
        try:
            dialog = GenericUploadDialog(
                executable=butler_exe,
                environment={
                    "BUTLER_API_KEY": f"{self.publish_profile.itch_config.api_key}",
                    "BUTLER_NO_TTY": "1",
                },
                title=self.publish_profile.project.name,
                arguments=arguments,
                display_info={  # Pass info for display in the dialog
                    "build_id": self.publish_profile.build_id,
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
                logging.info(
                    "Itch.io upload dialog closed with Rejected status (failed or cancelled)."
                )
            else:
                logging.info(
                    "Itch.io upload dialog closed with Accepted status (likely successful)."
                )

        except FileNotFoundError:
            # This might occur if butler_exe path is wrong before QProcess tries
            raise InvalidConfigurationError(
                f"Butler executable not found at '{butler_exe}'."
            )
        except Exception as e:
            logging.info(f"An error occurred launching or running the Itch upload dialog: {e}")
            raise
