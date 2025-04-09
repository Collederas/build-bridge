import os
from pathlib import Path


from PyQt6.QtWidgets import QDialog


from core.publisher.base_publisher import BasePublisher
from exceptions import InvalidConfigurationError
from database import SessionFactory
from models import ItchConfig

from views.dialogs.itch_upload_dialog import ItchUploadDialog


class ItchPublisher(BasePublisher):
    """
    Handles uploading builds to Itch.io using the 'butler' command-line tool
    by launching a dedicated upload dialog.
    """

    def __init__(self):
        self.session = SessionFactory()
        self.itch_config = self._load_config()

    def _load_config(self) -> ItchConfig:
        """Loads the Itch.io configuration from the database."""
        # Ensure the config is attached to the session if loaded
        config = self.session.query(ItchConfig).first()
        if not config:
            self.session.close()  # Close session if config loading fails early
            raise InvalidConfigurationError(
                "Itch.io configuration not found in settings."
            )
        if not config.itch_user_game_id:
            self.session.close()
            raise InvalidConfigurationError("Itch.io User/Game ID is not configured.")
        # Ensure object is associated with the session if it came from elsewhere
        if config not in self.session:
            self.session.add(config)
        return config

    def publish(self, content_dir: str, build_id: str, channel_name: str = None):
        """
        Prepares the butler command and launches the ItchUploadDialog to execute it.

        Args:
            content_dir: Path to the directory containing the built game files.
            build_id: The version or identifier for this build (e.g., "1.0.0").
            channel_name: The Itch.io channel name (e.g., "windows-beta", "linux").
        """
        print(f"Preparing Itch.io publish for build: {build_id}")

        if not self.itch_config:
            raise InvalidConfigurationError("Itch.io configuration not loaded.")

        # --- Determine Butler Executable ---
        butler_exe = self.itch_config.butler_path or "butler"


        api_key = self.itch_config.api_key
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

        itch_target = f"{self.itch_config.itch_user_game_id}:{channel_name}"

        # --- Construct Butler Command Arguments ---
        # Note: command executable is passed separately to QProcess
        arguments = [
            "push",
            str(Path(content_dir).resolve()),  # Ensure absolute path
            itch_target,
            "--userversion",
            build_id,
        ]

        # --- Prepare Environment ---
        # QProcess needs environment as a list of "key=value" strings


        print(f"Command: {butler_exe} {' '.join(arguments)}")
        print(f"Target: {itch_target}")

        # --- Launch Dialog ---
        try:
            # Assuming QApplication instance exists
            dialog = ItchUploadDialog(
                executable=butler_exe,
                api_key=api_key,
                arguments=arguments,
                display_info={  # Pass info for display in the dialog
                    "build_id": build_id,
                    "target": itch_target,
                    "content_dir": content_dir,
                },
            )
            # The dialog will handle QProcess execution and feedback
            result = dialog.exec()  # Show the dialog modally

            if result == QDialog.DialogCode.Rejected:
                # Check if rejection was due to failure or cancellation
                # The dialog itself should log the specific reason
                print(
                    "Itch.io upload dialog closed with Rejected status (failed or cancelled)."
                )
                # Optionally raise an error based on dialog's internal state if needed
                # raise RuntimeError("Itch.io upload failed or was cancelled.")
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
            raise  # Re-raise the exception
        finally:
            # Close the session after the dialog is done
            self.session.close()
