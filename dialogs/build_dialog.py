import logging
import os
import subprocess
import platform

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTextEdit,
    QPushButton,
    QHBoxLayout,
)
from PyQt6.QtCore import QProcess

from widgets.buildlist_widget import BuildListWidget
from builder.unreal_builder import UnrealBuilder

logger = logging.getLogger(__name__)


class BuildWindowDialog(QDialog):
    def __init__(self, builder: UnrealBuilder, parent=None):
        super().__init__(parent)
        self.builder = builder
        self.build_in_progress = False
        self.process = None
        self.setup_ui()
        self.start_build()

    def setup_ui(self):
        self.setWindowTitle("Unreal Engine Builder")
        self.setMinimumSize(600, 400)

        self.layout = QVBoxLayout()

        # Build output log
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMinimumHeight(200)  # Initial height, will adjust later
        self.layout.addWidget(self.output_text)

        # Button layout
        self.button_layout = QHBoxLayout()
        self.action_button = QPushButton("Cancel Build")
        self.action_button.clicked.connect(self.cancel_build)
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.action_button)

        # Build list widget (hidden until build completes)
        self.build_list_widget = BuildListWidget(None, self)
        self.build_list_widget.setVisible(False)
        self.layout.addWidget(self.build_list_widget)

        self.layout.addLayout(self.button_layout)
        self.setLayout(self.layout)

    def start_build(self):
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
            logger.info(f"Starting build with command: {program} {' '.join(arguments)}")

            self.process.start(program, arguments)

            self.action_button.setText("Cancel Build")
            self.action_button.clicked.connect(self.cancel_build)
            if not self.process.waitForStarted(5000):
                raise Exception(
                    f"Failed to start process: {self.process.errorString()}"
                )
        except Exception as e:
            self.append_output(f"Failed to start build: {str(e)}")
            logger.error(f"Build start failed: {str(e)}", exc_info=True)
            self.build_finished(-1, QProcess.ExitStatus.CrashExit)

    def handle_output(self):
        if self.build_in_progress:
            data = (
                self.process.readAllStandardOutput()
                .data()
                .decode("utf-8", errors="replace")
            )
            self.append_output(data)
            logger.debug(f"Process output: {data.strip()}")

    def cancel_build(self):
        """Immediately force-cancel the running build."""
        if not self.process or self.process.state() == QProcess.ProcessState.NotRunning:
            self.append_output("\nNo active build process to cancel.")
            return

        try:
            self.action_button.setEnabled(False)
            self.append_output("\nCancelling build (forcing termination)...")
            logger.info("Attempting to force-cancel build")

            pid = self.process.processId()
            if platform.system() == "Windows":
                result = subprocess.run(
                    f"taskkill /F /T /PID {pid}",
                    shell=True,
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    self.append_output("Build process and children terminated.")
                    logger.info(f"Process {pid} and children terminated via taskkill.")
                else:
                    self.append_output(f"WARNING: Termination failed: {result.stderr}")
                    logger.error(f"taskkill failed: {result.stderr}")
            else:
                # On Unix-like systems, kill the process group
                os.killpg(os.getpgid(pid), 9)  # SIGKILL
                self.append_output("Build process and children terminated.")
                logger.info(f"Process group {os.getpgid(pid)} terminated via SIGKILL.")

            # Wait briefly to confirm termination
            self.process.waitForFinished(2000)
            if self.process.state() != QProcess.ProcessState.NotRunning:
                self.append_output("WARNING: Process may still be running!")
                logger.error(f"Process {pid} may not have terminated.")

        except Exception as e:
            self.append_output(f"Cancel failed: {str(e)}")
            logger.error(f"Force cancel failed: {str(e)}", exc_info=True)
        finally:
            self.reset_after_cancel()

    def reset_after_cancel(self):
        self.build_in_progress = False
        if self.process:
            self.process.readyReadStandardOutput.disconnect()  # Stop output processing
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

    def handle_output(self):
        """Handle output from the QProcess."""
        data = (
            self.process.readAllStandardOutput()
            .data()
            .decode("utf-8", errors="replace")
        )
        self.append_output(data)
        logger.debug(f"Process output: {data.strip()}")

    def handle_error(self, error):
        """Handle QProcess errors."""
        self.append_output(f"Process error: {self.process.errorString()}\n")
        logger.error(f"Process error {error}: {self.process.errorString()}")

    def build_finished(self, exit_code, exit_status):
        """Handle build completion."""
        if exit_status == QProcess.ExitStatus.NormalExit and exit_code == 0:
            self.append_output("\nBUILD COMPLETED SUCCESSFULLY")
            logger.info("Build completed successfully")
            self.transition_to_build_management()
        else:
            self.append_output(f"\nBUILD FAILED (Exit code: {exit_code})")
            logger.warning(f"Build failed with exit code {exit_code}")
            self.action_button.setText("Close")
            self.action_button.clicked.disconnect()
            self.action_button.clicked.connect(self.close)

        self.action_button.setEnabled(True)

    def append_output(self, text: str):
        """Append text to the output widget."""
        try:
            self.output_text.append(text.strip())
            self.output_text.verticalScrollBar().setValue(
                self.output_text.verticalScrollBar().maximum()
            )
        except Exception as e:
            logger.error(f"Error updating GUI: {str(e)}", exc_info=True)

    def transition_to_build_management(self):
        self.setWindowTitle("Build Management")
        self.output_text.setMaximumHeight(150)
        self.build_list_widget.setVisible(True)
        self.build_list_widget.load_builds(os.path.basename(self.builder.output_dir))
        self.action_button.setText("Close")
        self.action_button.clicked.disconnect()
        self.action_button.clicked.connect(self.close)
