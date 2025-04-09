from pathlib import Path

# Note: Import QTimer
from PyQt6.QtCore import QProcess, QTimer
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QTextEdit,
    QLabel,
    QPushButton,
    QDialog,
    QHBoxLayout,
    QSpacerItem,
    QSizePolicy,
)

from models import SteamPublishProfile, SteamConfig


class SteamUploadDialog(QDialog):
    def __init__(self, publish_profile: SteamPublishProfile):
        super().__init__()
        self.publish_profile = publish_profile
        self.steam_config = publish_profile.steam_config
        self.vdf_file = Path(publish_profile.builder_path) / "app_build.vdf"
        self.steamcmd_path = Path(self.steam_config.steamcmd_path)

        self.process = None
        self._current_result_callback = None

        # --- UX Enhancement: Waiting Indicator ---
        self.wait_timer = QTimer(self)
        self.wait_timer.setSingleShot(True)
        self.wait_timer.setInterval(1500)
        self.wait_timer.timeout.connect(self.show_wait_indicator)

        self.animation_timer = QTimer(self)
        self.animation_timer.setInterval(500)
        self.animation_timer.timeout.connect(self.animate_wait_indicator)
        self.dot_count = 0
        # --- End UX Enhancement ---

        self.setup_ui()
        self.setup_process()
        self.setWindowTitle("Upload to Steam")

        # Start the upload process after UI setup
        self.start_upload()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Top info label
        main_layout.addWidget(
            QLabel(
                f"Uploading {self.publish_profile.project.name} using VDF: {self.vdf_file.name}\nFrom: {self.vdf_file.parent}"
            )
        )

        # Log display (takes up most space)
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        main_layout.addWidget(self.log_display, 1) # Add stretch factor

        # --- Bottom Layout for Indicator and Button ---
        bottom_layout = QHBoxLayout()

        # Indicator Label (Now more visible)
        self.wait_indicator_label = QLabel(" ")
        # Make it bold and use default color for visibility
        self.wait_indicator_label.setStyleSheet("font-weight: bold;")
        self.wait_indicator_label.hide() # Initially hidden
        bottom_layout.addWidget(self.wait_indicator_label)

        # Spacer to push button to the right
        bottom_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        # Cancel/Close Button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed) # Prevent button stretching
        self.cancel_btn.clicked.connect(self.cancel_process)
        bottom_layout.addWidget(self.cancel_btn)

        # Add bottom layout to main layout
        main_layout.addLayout(bottom_layout)
        # --- End Bottom Layout ---

        self.setLayout(main_layout)
        # Keep previous size or adjust if needed
        self.resize(600, 450)

    # setup_indicator function is removed as its logic is integrated into setup_ui

    def setup_process(self):
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyRead.connect(self.read_realtime_output)
        self.process.finished.connect(self.handle_process_finished)
        self.process.errorOccurred.connect(self.handle_process_error)

    # --- UX Enhancement: Indicator Control Methods ---
    def show_wait_indicator(self):
        self.dot_count = 1
        # Ensure the label text is updated correctly
        self.wait_indicator_label.setText("Upload in progress ")
        self.wait_indicator_label.show()
        # Start animation only when shown
        if not self.animation_timer.isActive():
            self.animation_timer.start()

    def animate_wait_indicator(self):
        # Ensure the label is visible before animating
        if not self.wait_indicator_label.isVisible():
            self.animation_timer.stop()
            return
        self.dot_count = (self.dot_count % 5) + 1
        dots = "." * self.dot_count
        self.wait_indicator_label.setText(f"Upload in progress {dots}")

    def hide_and_reset_wait_indicator(self):
        self.wait_timer.stop()
        self.animation_timer.stop()
        self.wait_indicator_label.hide()
        self.wait_indicator_label.setText(" ") # Reset text but keep space for layout stability if needed
    # --- End UX Enhancement Methods ---

    def read_realtime_output(self):
        # --- UX Enhancement: Output received ---
        self.hide_and_reset_wait_indicator()
        if self.process and self.process.state() == QProcess.ProcessState.Running:
             self.wait_timer.start() # Restart wait timer for next silence
        # --- End UX Enhancement ---

        try:
            data = self.process.readAll().data()
            # Decode with UTF-8, replacing errors, and strip whitespace
            # Decode as latin-1 first if UTF-8 fails often with steamcmd,
            # though UTF-8 is generally preferred.
            try:
                output = data.decode("utf-8", errors='replace').strip()
            except UnicodeDecodeError:
                 output = data.decode("latin-1", errors='replace').strip() # Fallback

            if output:
                self.log_display.append(output)
                # Ensure scrolling happens after text is appended
                self.log_display.verticalScrollBar().setValue(
                    self.log_display.verticalScrollBar().maximum()
                )
        except Exception as e:
            self.log_display.append(
                f"[Decode Error] Could not read process output: {e}"
            )

    def start_upload(self):
        # Check if steamcmd path is valid before proceeding
        if not self.steamcmd_path.is_file():
            self.log_display.append(
                f"[ERROR] Cannot start: steamcmd executable not found at '{self.steamcmd_path}'. Check Steam settings."
            )
            self.cancel_btn.setText("Close")
            try:
                # Disconnect all slots if any exist before connecting reject
                self.cancel_btn.clicked.disconnect()
            except TypeError:
                pass # No slots connected
            self.cancel_btn.clicked.connect(self.reject) # Allow closing the dialog
            return

        self.log_display.append(f"Starting SteamCMD upload using: {self.steamcmd_path}")
        self.log_display.append(f"Using VDF file: {self.vdf_file}")
        self.log_display.append(
            "Attempting login. Steam Guard prompt may appear (check authenticator/email)."
        )

        # Ensure VDF file path is absolute string
        vdf_file_path_str = str(self.vdf_file.resolve())

        command_args = [
            "+login",
            self.steam_config.username,
            self.steam_config.password,
            "+run_app_build",
            vdf_file_path_str,
            "+quit",
        ]

        # Ensure executable path is absolute string
        executable_path_str = str(self.steamcmd_path.resolve())

        self.run_command(
            executable_path_str, command_args, self.handle_upload_result
        )

    def run_command(self, executable: str, arguments: list[str], result_callback=None):
        # Check process state before starting
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.log_display.append(
                "[ERROR] Cannot start: Another process is already running."
            )
            return

        # Assign the callback for the specific command run
        self._current_result_callback = result_callback

        # Setup working directory
        executable_path_obj = Path(executable)
        working_dir = str(executable_path_obj.parent.resolve())
        self.process.setWorkingDirectory(working_dir)

        # Log command details
        # Ensure arguments with spaces are quoted for logging clarity
        log_args = " ".join(f'"{arg}"' if " " in arg else arg for arg in arguments)
        log_cmd = f'"{executable}" {log_args}'
        self.log_display.append(f"Working Directory: {working_dir}")
        self.log_display.append(f"Executing: {log_cmd}")
        print(f"[Debug run_command] Executable: {executable}")
        print(f"[Debug run_command] Arguments: {arguments}")
        print(f"[Debug run_command] Working Dir: {self.process.workingDirectory()}")

        # Start the process
        self.process.start(executable, arguments)

        # Check if process started successfully and start timer
        if self.process.state() == QProcess.ProcessState.Running:
            # --- UX Enhancement: Start waiting timer ---
            self.wait_timer.start()
            # --- End UX Enhancement ---
        elif self.process.state() == QProcess.ProcessState.NotRunning:
             # If start() failed immediately, handle_process_error should be called
             # Or log an additional message here if needed
             self.log_display.append("[ERROR] Process failed to start immediately.")


    def handle_upload_result(self, exit_code):
        self.hide_and_reset_wait_indicator()

        # --- Output Buffering Note ---
        # QProcess reads data when the *child process* (steamcmd) writes it to the output pipe.
        # QProcess won't receive data until steamcmd flushes its buffer (e.g., on newline,
        # when buffer is full, or program exits).
        # Therefore, output might appear delayed or arrive all at once at the end.
        log_content = self.log_display.toPlainText().lower()
        final_message = ""
        is_success = False

        # Check login status first
        login_ok = "logged in ok" in log_content
        steam_guard_required = "steam guard code required" in log_content or "two-factor authentication" in log_content
        login_failure_generic = "login failure" in log_content or ("password" in log_content and not login_ok) # Check password fail only if not logged in

        if not login_ok:
            # Handle various login failure scenarios
            if steam_guard_required:
                final_message = "Login failed: Steam Guard code required, refused, or timed out. Process terminated."
            elif login_failure_generic:
                final_message = "Login failed: Incorrect username or password. Process terminated."
            else:
                # Catch-all for other login phase failures or cancellations
                final_message = f"Login failed or was interrupted before completion (Exit Code: {exit_code}). Process terminated. Review logs."
        else:
            # Login was OK, now check for build success indicators
            # Add more specific success phrases if known from steamcmd output
            success_indicators = ["app build successful", "success", "uploaded", "build finished", "app content successfullycommited"] # Added another common one
            # Check if any indicator is present in the log
            build_successful = any(indicator in log_content for indicator in success_indicators)

            if exit_code == 0 and build_successful:
                final_message = "Upload appears to have completed successfully!"
                is_success = True
            elif exit_code == 0 and not build_successful:
                 # Exit code 0 but no clear success message found
                 final_message = f"Upload process finished (Exit Code: {exit_code}), but specific success message not found. Please review the logs carefully."
                 # Check for common failure messages even with exit code 0
                 if "failed" in log_content or "error" in log_content:
                      final_message += " Potential errors detected in log."
            else:
                 # Non-zero exit code usually indicates failure
                 final_message = f"Upload process failed or finished with errors after login (Exit Code: {exit_code}). Review logs."
            # is_success is determined above

        # Append final status summary to log display
        self.log_display.append("-" * 20)
        self.log_display.append(final_message)
        self.log_display.append("-" * 20)
        # Auto-scroll to the end
        self.log_display.verticalScrollBar().setValue(self.log_display.verticalScrollBar().maximum())

        # Update the button to "Close" and connect appropriate slot (accept/reject)
        self.cancel_btn.setText("Close")
        try:
            self.cancel_btn.clicked.disconnect() # Disconnect previous slots (like cancel_process)
        except TypeError:
            pass # No slots were connected

        if is_success:
            self.cancel_btn.clicked.connect(self.accept) # Close dialog successfully
        else:
            self.cancel_btn.clicked.connect(self.reject) # Close dialog indicating failure/issue


    def cancel_process(self):
        # --- UX Enhancement: Hide indicator ---
        self.hide_and_reset_wait_indicator()
        # --- End UX Enhancement ---

        # Terminate the running process if it exists and is running
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self.log_display.append("Attempting to terminate the process...")
            self.process.kill() # Send termination signal
            # Wait briefly for graceful termination, but don't hang indefinitely
            if not self.process.waitForFinished(2000): # Wait 2 seconds
                self.log_display.append(
                    "Process did not terminate gracefully after kill signal."
                )
            else:
                self.log_display.append("Process terminated by cancellation.")
            # The finished signal should still be emitted after kill/termination
        else:
            self.log_display.append("No active process running to cancel.")

        # If cancel was clicked while process was running, reject the dialog
        if self.cancel_btn.text() == "Cancel":
            self.log_display.append("Operation cancelled by user.")
            self.reject()
        # If button is "Close", the appropriate slot (accept/reject) is already connected


    def handle_process_finished(self, exit_code, exit_status):
        self.hide_and_reset_wait_indicator()

        status_str = (
            "NormalExit"
            if exit_status == QProcess.ExitStatus.NormalExit
            else "CrashExit"
        )
        # Log process end only if the callback hasn't already handled it or been cleared
        if self.process: # Check if process object still exists
             process_state = self.process.state()
             # Check if callback exists; implies this is the primary finish signal we should act upon
             if process_state == QProcess.ProcessState.NotRunning and hasattr(self, "_current_result_callback") and self._current_result_callback:
                self.log_display.append(
                    f"Process finished. Exit Code: {exit_code}, Status: {status_str}"
                )
                callback_to_run = self._current_result_callback
                self._current_result_callback = None # Clear callback *before* calling it

                try:
                    # Execute the specific result handler (e.g., handle_upload_result)
                    callback_to_run(exit_code)
                except Exception as e:
                     self.log_display.append(f"[ERROR] Error in result callback: {e}")
                     # Ensure button allows closing even if callback fails
                     if self.cancel_btn.text() != "Close":
                          self.cancel_btn.setText("Close")
                          try: self.cancel_btn.clicked.disconnect()
                          except TypeError: pass
                          self.cancel_btn.clicked.connect(self.reject)

             elif process_state == QProcess.ProcessState.NotRunning:
                 # Log if process finished but callback was already handled/cleared (e.g., after error or cancel)
                 self.log_display.append(f"Process ended (Code: {exit_code}, Status: {status_str}). Final state determined by previous actions.")


    def handle_process_error(self, error: QProcess.ProcessError):
        self.hide_and_reset_wait_indicator()

        error_messages = {
            QProcess.ProcessError.FailedToStart: "The process failed to start. Check executable path, permissions, and dependencies (like DLLs).",
            QProcess.ProcessError.Crashed: "The process crashed unexpectedly.",
            QProcess.ProcessError.Timedout: "The process timed out.",
            QProcess.ProcessError.WriteError: "An error occurred while writing to the process.",
            QProcess.ProcessError.ReadError: "An error occurred while reading from the process.",
            QProcess.ProcessError.UnknownError: "An unknown process error occurred.",
        }
        error_text = error_messages.get(
            error, f"An unexpected process error code ({error}) occurred."
        )
        self.log_display.append(f"[PROCESS ERROR] {error_text}")

        # Ensure the dialog can be closed on process error
        self.cancel_btn.setText("Close")
        try:
            self.cancel_btn.clicked.disconnect()
        except TypeError:
            pass
        self.cancel_btn.clicked.connect(self.reject) # Treat process errors as failure
        # Clear callback if an error occurs before finishing normally
        self._current_result_callback = None


    def cleanup(self):
        print(f"{self.__class__.__name__}: Running cleanup...")
        self.wait_timer.stop()
        self.animation_timer.stop()

        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            print(f"{self.__class__.__name__}: Terminating running process during cleanup...")
            # Disconnect signals to prevent issues during forced termination
            try: self.process.readyRead.disconnect()
            except TypeError: pass
            try: self.process.finished.disconnect()
            except TypeError: pass
            try: self.process.errorOccurred.disconnect()
            except TypeError: pass

            self.process.kill()
            if not self.process.waitForFinished(500):
                print(f"{self.__class__.__name__}: Process did not finish quickly after kill signal during cleanup.")
            print(f"{self.__class__.__name__}: Process terminated during cleanup.")
        elif self.process:
             print(f"{self.__class__.__name__}: Process already finished during cleanup.")
        else:
            print(f"{self.__class__.__name__}: No active process object found during cleanup.")
        # Help garbage collection
        self.process = None


    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)