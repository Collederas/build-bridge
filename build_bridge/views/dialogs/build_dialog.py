import os
import subprocess
import platform

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTextEdit,
    QPushButton,
    QHBoxLayout,
    QWidget,
    QCheckBox,
    QLineEdit,
)
from PyQt6.QtCore import QProcess, pyqtSignal, Qt
from PyQt6.QtGui import QIcon, QTextCursor, QTextDocument

from build_bridge.core.builder.unreal_builder import UnrealBuilder
from build_bridge.utils.paths import get_resource_path


class BuildWindowDialog(QDialog):
    build_ready_signal = pyqtSignal(str)  # payload = build_dir

    def __init__(self, builder: UnrealBuilder, parent=None):
        super().__init__(parent)
        self.builder = builder
        self.build_in_progress = False
        self.process = None
        self.filter_streaming = False  # Initialize filter_streaming
        self.setup_ui()
        self.start_build()

    def setup_ui(self):
        self.setWindowTitle("Unreal Engine Builder")
        self.setMinimumSize(600, 400)
        icon_path = str(get_resource_path("icons/buildbridge.ico"))
        self.setWindowIcon(QIcon(icon_path))

        self.layout = QVBoxLayout()
        self.layout.setSpacing(5)  # Reduce spacing for a compact look
        self.layout.setContentsMargins(5, 5, 5, 5)  # Reduce margins

        # Filter checkbox
        self.filter_checkbox = QCheckBox("Hide LogStreaming messages")
        self.filter_checkbox.stateChanged.connect(self.toggle_filter)
        self.layout.addWidget(self.filter_checkbox)

        # Search bar (hidden by default)
        self.search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search logs (Ctrl+F)")
        self.search_input.returnPressed.connect(self.find_next)
        self.search_input.textChanged.connect(self.reset_search)
        self.search_layout.addWidget(self.search_input)

        self.find_next_button = QPushButton("Next")
        self.find_next_button.clicked.connect(self.find_next)
        self.search_layout.addWidget(self.find_next_button)

        self.find_prev_button = QPushButton("Previous")
        self.find_prev_button.clicked.connect(self.find_prev)
        self.search_layout.addWidget(self.find_prev_button)

        self.search_layout_widget = QWidget()
        self.search_layout_widget.setLayout(self.search_layout)
        self.search_layout_widget.setVisible(False)
        self.layout.addWidget(self.search_layout_widget)

        # Build output log (single instance)
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMinimumHeight(200)
        self.output_text.setAcceptRichText(True)  # for color coding
        self.layout.addWidget(self.output_text)

        # Button layout (remove duplicate)
        self.button_layout = QHBoxLayout()
        self.action_button = QPushButton("Cancel Build")
        self.action_button.clicked.connect(self.cancel_build)
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.action_button)

        self.layout.addLayout(self.button_layout)
        self.setLayout(self.layout)

    def start_build(self):
        self.output_text.clear()

        try:
            if self.build_in_progress:
                self.append_output("A build is already in progress.")
                return

            self.build_in_progress = True
            self.process = QProcess(self)
            self.process.readyReadStandardOutput.connect(self.handle_output)
            self.process.finished.connect(self.build_finished)
            self.process.errorOccurred.connect(self.handle_error)

            command = self.builder.get_build_command()
            program = command[0]
            arguments = command[1:]

            self.append_output("Starting build...\n")
            self.append_output(f"Command: {program} {' '.join(arguments)}\n")
            print(f"Starting build with command: {program} {' '.join(arguments)}")

            self.process.start(program, arguments)

            self.action_button.setText("Cancel Build")
            self.action_button.clicked.connect(self.cancel_build)
            if not self.process.waitForStarted(5000):
                raise Exception(
                    f"ERROR: Failed to start process: {self.process.errorString()}"
                )
        except Exception as e:
            self.append_output(f"ERROR: Failed to start build: {str(e)}")
            print(f"Build start failed: {str(e)}", exc_info=True)
            self.build_finished(-1, QProcess.ExitStatus.CrashExit)

    def handle_output(self):
        if self.build_in_progress:
            data = (
                self.process.readAllStandardOutput()
                .data()
                .decode("utf-8", errors="replace")
            )
            self.append_output(data)
            print(f"Process output: {data.strip()}")

    def cancel_build(self):
        """Immediately force-cancel the running build."""
        if not self.process or self.process.state() == QProcess.ProcessState.NotRunning:
            self.append_output("\nWARNING: No active build process to cancel.")
            return

        try:
            self.action_button.setEnabled(False)
            self.append_output("\nWARNING: Cancelling build (forcing termination)...")
            print("Attempting to force-cancel build")

            pid = self.process.processId()
            if platform.system() == "Windows":
                result = subprocess.run(
                    f"taskkill /F /T /PID {pid}",
                    shell=True,
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    self.append_output("SUCCESS: Build process and children terminated.")
                    print(f"Process {pid} and children terminated via taskkill.")
                else:
                    self.append_output(f"WARNING: Termination failed: {result.stderr}")
                    print(f"taskkill failed: {result.stderr}")
            else:
                # On Unix-like systems, kill the process group
                os.killpg(os.getpgid(pid), 9)  # SIGKILL
                self.append_output("SUCCESS: Build process and children terminated.")
                print(f"Process group {os.getpgid(pid)} terminated via SIGKILL.")

            # Wait briefly to confirm termination
            self.process.waitForFinished(2000)
            if self.process.state() != QProcess.ProcessState.NotRunning:
                self.append_output("WARNING: Process may still be running!")
                print(f"Process {pid} may not have terminated.")

        except Exception as e:
            self.append_output(f"ERROR: Cancel failed: {str(e)}")
            print(f"Force cancel failed: {str(e)}", exc_info=True)
        finally:
            self.reset_after_cancel()

    def reset_after_cancel(self):
        self.build_in_progress = False
        if self.process:
            self.process.readyReadStandardOutput.disconnect()
        self.action_button.setText("Retry Build")
        self.action_button.clicked.disconnect()
        self.action_button.clicked.connect(self.start_build)
        self.action_button.setEnabled(True)

    def closeEvent(self, event):
        if self.build_in_progress:
            self.cancel_build()
        if self.process:
            if self.process.state() != QProcess.ProcessState.NotRunning:
                self.cancel_build()
            self.process.disconnect()
            self.process = None
        event.accept()

    def handle_error(self):
        """Handle QProcess errors."""
        self.append_output(f"ERROR: Process error: {self.process.errorString()}\n")
        print(f"Process error: {self.process.errorString()}")

    def build_finished(self, exit_code, exit_status):
        """Handle build completion."""
        if exit_status == QProcess.ExitStatus.NormalExit and exit_code == 0:
            self.append_output("\nSUCCESS: BUILD COMPLETED SUCCESSFULLY")
            print("Build completed successfully")
            self.action_button.setText("Close")
            self.build_ready_signal.emit(str(self.builder.output_dir))
            self.action_button.clicked.connect(self.accept)
        else:
            self.append_output(f"\nERROR: BUILD FAILED (Exit code: {exit_code})")
            print(f"Build failed with exit code {exit_code}")
            self.action_button.setText("Close")

            self.action_button.clicked.disconnect()
            self.action_button.clicked.connect(self.close)

        self.action_button.setEnabled(True)

    def append_output(self, text: str):
        try:
            lines = text.strip().split("\n")
            for line in lines:
                if not line.strip():
                    continue
                if self.filter_streaming and "LOGSTREAMING:" in line.upper():
                    continue  # Skip LogStreaming lines if filter enabled
                line_upper = line.upper()
                if ":" in line:
                    category = line.split(":", 1)[0]
                    formatted_line = f"<b>{category}</b>:{line[len(category) + 1:]}"
                else:
                    formatted_line = line
                if "ERROR:" in line_upper or ": ERROR" in line_upper:
                    formatted_text = f'<span style="color: red;">{formatted_line}</span>'
                elif "WARNING:" in line_upper or ": WARNING" in line_upper:
                    formatted_text = f'<span style="color: orange;">{formatted_line}</span>'
                elif "SUCCESS:" in line_upper:
                    formatted_text = f'<span style="color: green;">{formatted_line}</span>'
                elif "LOGCOOK:" in line_upper or "COOKED PACKAGES" in line_upper:
                    formatted_text = f'<span style="color: blue;">{formatted_line}</span>'
                else:
                    formatted_text = formatted_line
                self.output_text.append(formatted_text)
            self.output_text.verticalScrollBar().setValue(
                self.output_text.verticalScrollBar().maximum()
            )
        except Exception as e:
            print(f"Error updating GUI: {str(e)}", exc_info=True)

    def toggle_filter(self, state):
        self.filter_streaming = state == 2  # Checked state

    def keyPressEvent(self, event):
        """Handle Ctrl+F to toggle search bar."""
        if event.key() == Qt.Key.Key_F and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.search_layout_widget.setVisible(not self.search_layout_widget.isVisible())
            if self.search_layout_widget.isVisible():
                self.search_input.setFocus()
                self.search_input.selectAll()
            else:
                self.output_text.setFocus()
        else:
            super().keyPressEvent(event)

    def find_next(self):
        """Find the next occurrence of the search query."""
        query = self.search_input.text()
        if query:
            found = self.output_text.find(query)
            if not found:
                # Wrap around to the start
                cursor = self.output_text.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.Start)
                self.output_text.setTextCursor(cursor)
                self.output_text.find(query)

    def find_prev(self):
        """Find the previous occurrence of the search query."""
        query = self.search_input.text()
        if query:
            found = self.output_text.find(query, QTextDocument.FindFlag.FindBackward)
            if not found:
                # Wrap around to the end
                cursor = self.output_text.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.output_text.setTextCursor(cursor)
                self.output_text.find(query, QTextDocument.FindFlag.FindBackward)

    def reset_search(self):
        """Reset the cursor when the search query changes."""
        cursor = self.output_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.output_text.setTextCursor(cursor)