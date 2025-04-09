import sys
from pathlib import Path
from PyQt6.QtCore import QProcess
from PyQt6.QtWidgets import QVBoxLayout, QTextEdit, QLabel, QPushButton, QDialog

from models import SteamPublishProfile


class SteamUploadDialog(QDialog):
    """
    A dialog window to manage and display the output of uploading
    a build to Steam using steamcmd.
    This version directly calls steamcmd without using winpty.
    """

    def __init__(self, publish_profile: SteamPublishProfile):
        """
        Initializes the dialog.

        Args:
            publish_profile: An object containing Steam configuration
                             (username, password, steamcmd_path) and
                             the path to the VDF builder file.
        """
        super().__init__()
        self.steam_config = publish_profile.steam_config
        # Ensure vdf_file path is correctly constructed
        self.vdf_file = Path(publish_profile.builder_path) / "app_build.vdf"
        self.steamcmd_path = Path(
            self.steam_config.steamcmd_path
        )  # Store as Path object

        # Validate steamcmd path
        if not self.steamcmd_path.is_file():
            # Handle error appropriately - maybe raise an exception or show a message
            print(f"[ERROR] steamcmd not found at: {self.steamcmd_path}")
            # Potentially disable functionality or close dialog here
            # For now, we'll let it proceed and fail during execution

        self.process = None

        self.setup_ui()
        self.setup_process()
        self.setWindowTitle("Upload to Steam")

        self.start_upload()

    def setup_ui(self):
        """Sets up the user interface elements of the dialog."""
        layout = QVBoxLayout(self)  # Set layout parent
        layout.addWidget(
            QLabel(
                f"Uploading {self.publish_profile.project.name} using VDF: {self.vdf_file.name}\nFrom: {self.vdf_file.parent}"
            )
        )
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.log_display)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_process)
        layout.addWidget(self.cancel_btn)
        self.setLayout(layout)
        self.resize(600, 400)  # Set a reasonable default size

    def setup_process(self):
        """Configures the QProcess object for running external commands."""
        self.process = QProcess(self)
        # Merge stdout and stderr for unified output reading

        # --- Output Buffering Note ---
        # QProcess reads data when the *child process* (steamcmd) writes it to the output pipe.
        # If steamcmd buffers its output (common when not run in an interactive terminal),
        # QProcess won't receive data until steamcmd flushes its buffer (e.g., on newline,
        # when buffer is full, or program exits). QProcess cannot force steamcmd to be unbuffered.
        # Tools like 'winpty' (previously removed) or other PTY wrappers are often needed on
        # Windows to make steamcmd *think* it's in an interactive session and use less buffering.
        # Therefore, output might appear delayed or arrive all at once at the end.
        # ---
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyRead.connect(self.read_realtime_output)
        # Connect finished and error signals *generically* here
        self.process.finished.connect(self.handle_process_finished)
        self.process.errorOccurred.connect(self.handle_process_error)

    def read_realtime_output(self):
        """Reads and displays output from the running process in real-time."""
        try:
            # Read all available data from the merged channel
            data = self.process.readAll().data()
            # Attempt to decode using UTF-8, replacing errors
            output = data.decode("utf-8", errors="replace").strip()
            if output:
                self.log_display.append(output)
                # Auto-scroll to the bottom
                self.log_display.verticalScrollBar().setValue(
                    self.log_display.verticalScrollBar().maximum()
                )
        except Exception as e:
            self.log_display.append(
                f"[Decode Error] Could not read process output: {e}"
            )

    def start_upload(self):
        """Initiates the steamcmd upload process."""
        if not self.steamcmd_path.is_file():
            self.log_display.append(
                f"[ERROR] Cannot start: steamcmd executable not found at '{self.steamcmd_path}'."
            )
            self.cancel_btn.setText("Close")
            try:
                self.cancel_btn.clicked.disconnect()
            except TypeError:
                pass
            self.cancel_btn.clicked.connect(self.reject)
            return

        self.log_display.append(f"Starting SteamCMD upload using: {self.steamcmd_path}")
        self.log_display.append(f"Using VDF file: {self.vdf_file}")
        self.log_display.append(
            "Steam Guard prompt may appear (check authenticator/email)."
        )

        # Construct the command arguments for steamcmd
        command_args = [
            "+login",
            self.steam_config.username,
            self.steam_config.password,
            "+run_app_build",
            str(self.vdf_file.resolve()),  # Use absolute path for VDF
            "+quit",
        ]

        # Execute the command directly using steamcmd executable
        self.run_command(
            str(self.steamcmd_path.resolve()), command_args, self.handle_upload_result
        )

    def run_command(self, executable: str, arguments: list[str], result_callback=None):
        """
        Runs an external command using QProcess.

        Args:
            executable (str): The absolute path to the executable.
            arguments (list[str]): A list of arguments for the command.
            result_callback (callable, optional): A function to call when the
                                                  process finishes, receiving the exit code.
        """
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.log_display.append(
                "[ERROR] Cannot start: Another process is already running."
            )
            return

        # Disconnect previous specific finished handler if any
        try:
            # Note: Disconnecting lambdas directly can be tricky.
            # It's often better to manage connections carefully or use named slots.
            # For simplicity here, we assume the generic finished handler is sufficient
            # and the result_callback handles the specific logic.
            # If precise disconnection is needed, manage connections more explicitly.
            pass  # self.process.finished.disconnect() # Be cautious with this
        except TypeError:
            pass  # No connection to disconnect

        # Store the specific callback if provided
        self._current_result_callback = result_callback

        # Set the working directory to the executable's directory
        # This helps steamcmd find its required DLLs/files.
        executable_path = Path(executable)
        working_dir = str(executable_path.parent.resolve())
        self.process.setWorkingDirectory(working_dir)

        # Log the command execution details
        log_cmd = f'"{executable}"' + (
            " " + " ".join(f'"{arg}"' if " " in arg else arg for arg in arguments)
            if arguments
            else ""
        )
        self.log_display.append(f"Working Directory: {working_dir}")
        self.log_display.append(f"Executing: {log_cmd}")
        print(f"[Debug run_command] Executable: {executable}")
        print(f"[Debug run_command] Arguments: {arguments}")
        print(f"[Debug run_command] Working Dir: {self.process.workingDirectory()}")

        # Start the process
        self.process.start(executable, arguments)

    def handle_upload_result(self, exit_code):
        """
        Analyzes the result of the steamcmd upload process based on exit code and log output.
        This is called specifically after the upload command finishes.
        """
        output = self.log_display.toPlainText().lower()  # Get all log text

        # Define success indicators (adjust based on actual steamcmd output)
        success_indicators = ["app build successful", "success", "uploaded", "finished"]
        login_ok = "logged in ok" in output
        steam_guard_required = (
            "steam guard code required" in output
            or "two-factor authentication" in output
        )

        final_message = ""
        is_success = False

        if exit_code == 0 and any(
            indicator in output for indicator in success_indicators
        ):
            final_message = "Upload appears to have completed successfully!"
            is_success = True
        elif steam_guard_required:
            final_message = "Login failed: Steam Guard code required. Please check your authenticator/email."
        elif not login_ok and ("password" in output or "login failure" in output):
            final_message = "Login failed. Please check username/password."
        else:
            # General failure or uncertain outcome
            final_message = f"Upload finished with exit code {exit_code}, but success message not clearly found. Please review the logs above."
            if exit_code != 0:
                final_message += f" (Exit code indicates an error: {exit_code})"

        self.log_display.append("-" * 20)
        self.log_display.append(final_message)
        self.log_display.append("-" * 20)

        # Update button based on outcome
        self.cancel_btn.setText("Close")
        try:
            self.cancel_btn.clicked.disconnect()
        except TypeError:
            pass

        if is_success:
            self.cancel_btn.clicked.connect(self.accept)  # Close dialog successfully
        else:
            self.cancel_btn.clicked.connect(
                self.reject
            )  # Close dialog indicating failure

    def cancel_process(self):
        """Attempts to terminate the running process or closes the dialog."""
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self.log_display.append("Attempting to terminate the process...")
            self.process.kill()  # Send terminate signal
            if not self.process.waitForFinished(3000):  # Wait up to 3 seconds
                self.log_display.append(
                    "Process did not terminate gracefully, forcing kill."
                )
                # Note: QProcess.kill() on Windows often forcefully terminates.
            else:
                self.log_display.append("Process terminated.")
        else:
            self.log_display.append("No process running to cancel.")

        # Close the dialog - reject if cancelled, accept if it was already finished and 'Close' was clicked
        if self.cancel_btn.text() == "Cancel":
            self.reject()  # Indicate cancellation
        else:
            # If button is "Close", the outcome (accept/reject) was set in handle_upload_result
            # The connected slot (accept or reject) will handle closing.
            pass

    def handle_process_finished(self, exit_code, exit_status):
        """
        Generic handler called whenever the QProcess finishes, regardless of how.
        """
        status_str = (
            "NormalExit"
            if exit_status == QProcess.ExitStatus.NormalExit
            else "CrashExit"
        )
        # Check state again because errorOccurred might also trigger closing actions
        if self.process.state() == QProcess.ProcessState.NotRunning:
            self.log_display.append(
                f"Process finished. Exit Code: {exit_code}, Status: {status_str}"
            )
            # Call the specific result handler if one was set for the last command
            if (
                hasattr(self, "_current_result_callback")
                and self._current_result_callback
            ):
                try:
                    self._current_result_callback(exit_code)
                except Exception as e:
                    self.log_display.append(f"[ERROR] Error in result callback: {e}")
                finally:
                    self._current_result_callback = (
                        None  # Clear callback after execution
                    )

    def handle_process_error(self, error: QProcess.ProcessError):
        """Handles errors reported by the QProcess object itself."""
        error_messages = {
            QProcess.ProcessError.FailedToStart: "The process failed to start. Check executable path, permissions, and dependencies (like DLLs).",
            QProcess.ProcessError.Crashed: "The process crashed unexpectedly.",
            QProcess.ProcessError.Timedout: "The process timed out (less common with default settings).",
            QProcess.ProcessError.WriteError: "An error occurred while writing to the process.",
            QProcess.ProcessError.ReadError: "An error occurred while reading from the process.",
            QProcess.ProcessError.UnknownError: "An unknown process error occurred.",
        }
        error_text = error_messages.get(
            error, f"An unexpected error code ({error}) occurred."
        )
        self.log_display.append(f"[PROCESS ERROR] {error_text}")

        # Ensure the dialog can be closed on error
        self.cancel_btn.setText("Close")
        try:
            self.cancel_btn.clicked.disconnect()
        except TypeError:
            pass
        self.cancel_btn.clicked.connect(self.reject)  # Treat process errors as failure

    def cleanup(self):
        """Ensures the QProcess is terminated when the dialog is closed or destroyed."""
        print(f"{self.__class__.__name__}: Running cleanup...")
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            print(f"{self.__class__.__name__}: Terminating running process...")
            self.process.kill()
            if not self.process.waitForFinished(500):  # Brief wait
                print(
                    f"{self.__class__.__name__}: Process did not finish quickly after kill signal."
                )
            self.process = None  # Release reference
            print(f"{self.__class__.__name__}: Process terminated.")
        else:
            print(f"{self.__class__.__name__}: No active process found during cleanup.")

    def closeEvent(self, event):
        """Override closeEvent to ensure cleanup runs when the dialog is closed."""
        self.cleanup()
        super().closeEvent(event)

    def __del__(self):
        """Ensure cleanup runs if the object is garbage collected (less reliable than closeEvent)."""
        self.cleanup()
