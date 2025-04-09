from pathlib import Path
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QLabel, QDialogButtonBox
from PyQt6.QtCore import QProcess, QProcessEnvironment


class ItchUploadDialog(QDialog):
    """
    A dialog window to display real-time output from the Itch.io 'butler' tool
    during the upload process using QProcess.
    """

    def __init__(
        self,
        executable: str,
        api_key: str,
        arguments: list[str],
        display_info: dict,
        parent=None,
    ):
        super().__init__(parent)
        self.executable = executable
        self.arguments = arguments

        self.display_info = display_info
        self.api_key = api_key

        self.process: QProcess | None = None
        self.upload_successful = False  

        # --- Timers for UX (Optional, like SteamUploadDialog) ---
        # self.wait_timer = QTimer(self) ...
        # self.animation_timer = QTimer(self) ...

        self.setup_ui()
        self.setup_process()
        self.setWindowTitle(
            f"Itch.io Upload: {self.display_info.get('build_id', '...')}"
        )

        # Start the upload automatically after UI setup
        self.start_upload()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Info Label ---
        info_text = (
            f"Uploading Build: {self.display_info.get('build_id', 'N/A')}\n"
            f"Target: {self.display_info.get('target', 'N/A')}\n"
            f"Source: {self.display_info.get('content_dir', 'N/A')}"
        )
        main_layout.addWidget(QLabel(info_text))

        # --- Log Display ---
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setLineWrapMode(
            QTextEdit.LineWrapMode.NoWrap
        )  # Keep butler's formatting
        self.log_display.setFontFamily("monospace")  # Good for console output
        main_layout.addWidget(self.log_display, 1)  # Stretch vertically

        # --- Status/Wait Indicator (Optional) ---
        # self.wait_indicator_label = QLabel(" ") ...
        # bottom_layout = QHBoxLayout() ... add indicator here

        # --- Buttons ---
        self.button_box = QDialogButtonBox()
        # Add Cancel button initially
        self.cancel_button = self.button_box.addButton(
            QDialogButtonBox.StandardButton.Cancel
        )
        self.cancel_button.clicked.connect(self.cancel_process)

        # Add button box to layout (or bottom_layout if using indicator)
        main_layout.addWidget(self.button_box)

        self.setLayout(main_layout)
        self.resize(700, 500)  # Adjust size as needed

    def setup_process(self):
        self.process = QProcess(self)
        process_env = QProcessEnvironment.systemEnvironment()
        process_env.insert("BUTLER_API_KEY", f"{self.api_key}")
        process_env.insert("BUTLER_NO_TTY", "1")

        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        # Connect signals
        self.process.readyReadStandardOutput.connect(self.read_realtime_output)
        self.process.finished.connect(self.handle_process_finished)
        self.process.errorOccurred.connect(self.handle_process_error)

    def start_upload(self):
        # Basic check for executable existence (QProcess might fail later anyway)
        if not Path(self.executable).exists():
            self.append_log(
                f"[ERROR] Cannot start: Butler executable not found at '{self.executable}'."
            )
            self.cancel_button.setText("Close")
            try:
                self.cancel_button.clicked.disconnect()
            except TypeError:
                pass
            self.cancel_button.clicked.connect(self.reject)
            return

        self.append_log(f"Starting Itch.io upload...")
        self.append_log(f"Executable: {self.executable}")
        self.append_log(f"Arguments: {' '.join(self.arguments)}")
        self.append_log("-" * 20)

        # QProcess needs the program and arguments separately
        self.process.start(self.executable, self.arguments)

        # Optional: Check if started successfully
        if not self.process.waitForStarted(5000):  # Wait 5 seconds
            self.append_log(
                f"[ERROR] Process failed to start: {self.process.errorString()}"
            )
            self.handle_process_finished(
                -1, QProcess.ExitStatus.CrashExit
            )  # Treat as failure

    def read_realtime_output(self):
        if not self.process:
            return
        try:
            data = self.process.readAllStandardOutput().data()
            # Butler output is usually UTF-8
            output = data.decode("utf-8", errors="replace").strip()
            if output:
                self.append_log(output)
        except Exception as e:
            self.append_log(f"[Decode Error] Could not read process output: {e}")

    def append_log(self, text: str):
        """Appends text to the log display and scrolls to the bottom."""
        self.log_display.append(text)
        # Ensure the view scrolls down automatically
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def cancel_process(self):
        """Attempts to terminate the running process."""
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self.append_log("-" * 20)
            self.append_log("Attempting to cancel upload...")
            self.process.kill()  # Send kill signal
            if not self.process.waitForFinished(2000):  # Wait briefly
                self.append_log(
                    "Warning: Process did not terminate quickly after kill signal."
                )
            else:
                self.append_log("Process terminated by cancellation.")
            # finished signal should still be emitted
        else:
            # If Cancel is clicked when process isn't running (e.g., after finish/error)
            self.reject()  # Just close the dialog

    def handle_process_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        """Handles the QProcess finished signal."""
        if self.process is None:
            return  # Avoid issues if called after cleanup

        status_str = (
            "Normal Exit"
            if exit_status == QProcess.ExitStatus.NormalExit
            else "Crash Exit"
        )
        self.append_log("-" * 20)
        self.append_log(
            f"Process finished. Exit Code: {exit_code}, Status: {status_str}"
        )

        # --- Determine Success/Failure ---
        # Simple check: exit code 0 is usually success for butler push
        log_content = self.log_display.toPlainText().lower()  # Get all logs
        # Butler typically indicates success clearly
        success_indicators = [
            "build is processed",
            "patch applied",
            "all tasks ended.",
        ]  # Add more if needed
        # Look for explicit error messages
        error_indicators = [
            "error:",
            "failed",
            "panic:",
            "invalid api key",
            "no such host",
        ]

        if exit_code == 0 and not any(err in log_content for err in error_indicators):
            # Consider successful if exit code is 0 and no obvious errors in log
            # Butler output might vary, adjust success_indicators if needed.
            self.append_log("Upload appears to have completed successfully!")
            self.upload_successful = True
        else:
            self.append_log("Upload failed or finished with errors.")
            self.upload_successful = False
            # You could add more specific error parsing here based on butler's output

        # --- Update UI ---
        self.button_box.clear()  # Remove Cancel button
        # Add Close button
        close_button = self.button_box.addButton(QDialogButtonBox.StandardButton.Close)

        if self.upload_successful:
            close_button.clicked.connect(self.accept)  # Close with Accept on success
        else:
            close_button.clicked.connect(
                self.reject
            )  # Close with Reject on failure/cancel

        # Ensure process object is cleaned up if needed immediately
        # self.process = None

    def handle_process_error(self, error: QProcess.ProcessError):
        """Handles errors emitted by QProcess itself (e.g., failed to start)."""
        if not self.process:
            return

        error_map = {
            QProcess.ProcessError.FailedToStart: "Failed to start the butler process. Check executable path and permissions.",
            QProcess.ProcessError.Crashed: "The butler process crashed.",
            QProcess.ProcessError.Timedout: "Process timed out (shouldn't normally happen here).",
            QProcess.ProcessError.ReadError: "Error reading from butler process.",
            QProcess.ProcessError.WriteError: "Error writing to butler process.",
            QProcess.ProcessError.UnknownError: "An unknown process error occurred.",
        }
        error_text = error_map.get(error, f"Unknown QProcess error code ({error})")

        self.append_log(f"[PROCESS ERROR] {error_text}")

        # Update UI to allow closing
        self.button_box.clear()
        close_button = self.button_box.addButton(QDialogButtonBox.StandardButton.Close)
        close_button.clicked.connect(self.reject)  # Treat process errors as failure
        self.upload_successful = False

    def cleanup(self):
        """Ensure the process is terminated if still running."""
        print(f"{self.__class__.__name__}: Running cleanup...")
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            print(
                f"{self.__class__.__name__}: Terminating running process during cleanup..."
            )
            # Disconnect signals to prevent issues during forced termination
            try:
                self.process.readyReadStandardOutput.disconnect()
            except TypeError:
                pass
            try:
                self.process.finished.disconnect()
            except TypeError:
                pass
            try:
                self.process.errorOccurred.disconnect()
            except TypeError:
                pass

            self.process.kill()
            if not self.process.waitForFinished(500):  # Brief wait
                print(
                    f"{self.__class__.__name__}: Process did not finish quickly after kill signal."
                )
            print(f"{self.__class__.__name__}: Process terminated during cleanup.")
        self.process = None  # Help garbage collection

    def closeEvent(self, event):
        """Called when the dialog is closed by the user (e.g., clicking X)."""
        self.cleanup()  # Ensure process is killed
        # Accept or reject based on success flag? Or always reject on manual close?
        # Default QDialog behavior on close is Reject. Let's stick with that.
        super().closeEvent(event)
