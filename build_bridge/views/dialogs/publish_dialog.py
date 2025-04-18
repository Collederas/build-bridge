from pathlib import Path
from typing import Callable, List, Dict, Optional

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTextEdit,
    QLabel,
    QDialogButtonBox,
    QWidget,
)
from PyQt6.QtCore import QProcess, QProcessEnvironment
from PyQt6.QtGui import QIcon

from build_bridge.utils.paths import get_resource_path


class GenericUploadDialog(QDialog):
    """
    A generic dialog to display real-time output from an external command-line process
    (like steamcmd or butler) using QProcess. Success determination is delegated.
    """

    def __init__(
        self,
        executable: str,
        arguments: List[str],
        display_info: Dict[str, str],  # For top label
        title: str,
        # Function signature: (exit_code: int, log_content: str) -> bool
        # This is the one thing that changes between stores.
        success_checker: Callable[[int, str], bool],
        environment: Optional[Dict[str, str]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.executable = executable
        self.arguments = arguments
        self.environment = environment
        self.display_info = display_info
        self.success_checker = success_checker  # Function to check success

        self.process: Optional[QProcess] = None
        self.upload_successful: bool = False  # Determined by success_checker
        self._log_buffer: str = ""  # Accumulate log content

        self.setWindowTitle(title)
        icon_path = str(get_resource_path("icons/buildbridge.ico"))
        self.setWindowIcon(QIcon(icon_path))

        self.setup_ui()
        self.setup_process()

        # Start the process automatically
        self.start_process()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Info Label ---
        # Construct info text from display_info dictionary dynamically
        info_lines = [
            f"{key.replace('_', ' ').title()}: {value}"
            for key, value in self.display_info.items()
        ]
        info_text = "\n".join(info_lines)
        main_layout.addWidget(QLabel(info_text))

        # --- Log Display ---
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.log_display.setFontFamily("monospace")
        main_layout.addWidget(self.log_display, 1)

        # --- Buttons ---
        self.button_box = QDialogButtonBox()
        self.cancel_button = self.button_box.addButton(
            QDialogButtonBox.StandardButton.Cancel
        )
        self.cancel_button.clicked.connect(self.cancel_process)
        main_layout.addWidget(self.button_box)

        self.setLayout(main_layout)
        self.resize(700, 500)

    def setup_process(self):
        self.process = QProcess(self)
        process_env = QProcessEnvironment.systemEnvironment()

        if self.environment:
            for k, v in self.environment.items():
                process_env.insert(k, v)

        self.process.setProcessEnvironment(process_env)

        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        # Connect signals
        self.process.readyReadStandardOutput.connect(self.read_realtime_output)
        self.process.finished.connect(self.handle_process_finished)
        self.process.errorOccurred.connect(self.handle_process_error)

    def start_process(self):
        if not self.process:
            return

        if not Path(self.executable).exists():
            self.append_log(
                f"[ERROR] Cannot start: Executable not found at '{self.executable}'."
            )
            self.cancel_button.setText("Close")
            try:
                self.cancel_button.clicked.disconnect()
            except TypeError:
                pass
            self.cancel_button.clicked.connect(self.reject)
            return

        self.append_log(f"Starting process via cmd /c...")
        self.append_log(f"Executable: {self.executable}")
        self.append_log(f"Arguments: {' '.join(self.arguments)}")
        self.append_log("-" * 20)

        # Run steamcmd through cmd /c
        cmd_arguments = ["/c", str(self.executable)] + self.arguments
        self.process.start("cmd", cmd_arguments)

        if not self.process.waitForStarted(5000):
            self.append_log(
                f"[ERROR] Process failed to start: {self.process.errorString()}"
            )
            # Simulate finish with failure status
            self.handle_process_finished(-1, QProcess.ExitStatus.CrashExit)

    def read_realtime_output(self):
        if not self.process:
            return
        try:
            data = self.process.readAllStandardOutput().data()
            # Try decoding UTF-8, fallback to latin-1 (common for console apps)
            try:
                output = data.decode("utf-8", errors="replace")
            except UnicodeDecodeError:
                output = data.decode("latin-1", errors="replace")

            # Append to both internal buffer and UI display
            if output:
                self._log_buffer += output
                self.append_log(output.rstrip())  # Avoid extra newlines in UI

        except Exception as e:
            self.append_log(f"[Decode Error] Could not read process output: {e}")

    def append_log(self, text: str):
        self.log_display.append(text)
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def cancel_process(self):
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self.append_log("-" * 20)
            self.append_log("Attempting to cancel process...")
            self.process.kill()
            if not self.process.waitForFinished(2000):
                self.append_log(
                    "Warning: Process did not terminate quickly after kill signal."
                )
            else:
                self.append_log("Process terminated by cancellation.")
            # finished signal will be emitted
        else:
            self.reject()  # Close dialog if process not running

    def handle_process_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        if self.process is None:
            return

        status_str = (
            "Normal Exit"
            if exit_status == QProcess.ExitStatus.NormalExit
            else "Crash Exit"
        )
        self.append_log("-" * 20)
        self.append_log(
            f"Process finished. Exit Code: {exit_code}, Status: {status_str}"
        )

        # --- Delegate Success Check ---
        try:
            self.upload_successful = self.success_checker(exit_code, self._log_buffer)
            if self.upload_successful:
                self.append_log("Operation reported as SUCCESSFUL.")
            else:
                self.append_log("Operation reported as FAILED or incomplete.")
        except Exception as e:
            self.append_log(f"[ERROR] Error occurred during success check: {e}")
            self.upload_successful = False
        # --- End Delegate Success Check ---

        # Update buttons
        self.button_box.clear()
        close_button = self.button_box.addButton(QDialogButtonBox.StandardButton.Close)
        if self.upload_successful:
            close_button.clicked.connect(self.accept)
        else:
            close_button.clicked.connect(self.reject)

    def handle_process_error(self, error: QProcess.ProcessError):
        if not self.process:
            return
        error_text = "Unknown QProcess error"
        self.append_log(f"[PROCESS ERROR] {error_text}")

        # Update UI for failure
        self.button_box.clear()
        close_button = self.button_box.addButton(QDialogButtonBox.StandardButton.Close)
        close_button.clicked.connect(self.reject)
        self.upload_successful = False

    def cleanup(self):
        print(f"{self.__class__.__name__}: Running cleanup...")
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            print(f"{self.__class__.__name__}: Terminating running process...")
            # Disconnect signals first
            try:
                self.process.readyReadStandardOutput.disconnect()
            except TypeError:
                pass
            # ... disconnect others ...
            self.process.kill()
            self.process.waitForFinished(500)
        self.process = None

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)
