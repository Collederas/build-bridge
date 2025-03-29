import logging
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QApplication
from PyQt6.QtCore import Qt, QProcess

from builder.unreal_builder import UnrealBuilder  # Adjust import path as needed

logger = logging.getLogger(__name__)

class BuildWindowDialog(QDialog):
    def __init__(self, builder: UnrealBuilder, parent=None):
        super().__init__(parent)
        self.builder = builder
        self.build_in_progress = False
        self.setup_ui()
        self.start_build()

    def setup_ui(self):
        self.setWindowTitle("Unreal Engine Builder")
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout()
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        layout.addWidget(self.output_text)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)

        self.cancel_button = QPushButton("Cancel Build")
        self.cancel_button.clicked.connect(self.cancel_build)
        layout.addWidget(self.cancel_button, alignment=Qt.AlignmentFlag.AlignRight)

        self.setLayout(layout)

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

            self.close_button.setEnabled(False)
            self.process.start(program, arguments)
            if not self.process.waitForStarted(5000):  # 5-second timeout
                raise Exception(f"Failed to start process: {self.process.errorString()}")
        except Exception as e:
            self.append_output(f"Failed to start build: {str(e)}")
            logger.error(f"Build start failed: {str(e)}", exc_info=True)
            self.build_finished(-1, QProcess.ExitStatus.CrashExit)

    def handle_output(self):
        """Handle output from the QProcess."""
        data = self.process.readAllStandardOutput().data().decode('utf-8', errors='replace')
        self.append_output(data)
        logger.debug(f"Process output: {data.strip()}")

    def handle_error(self, error):
        """Handle QProcess errors."""
        self.append_output(f"Process error: {self.process.errorString()}\n")
        logger.error(f"Process error {error}: {self.process.errorString()}")

    def build_finished(self, exit_code, exit_status):
        """Handle build completion."""
        try:
            if exit_status == QProcess.ExitStatus.NormalExit and exit_code == 0:
                self.append_output("\nBUILD COMPLETED SUCCESSFULLY")
                logger.info("Build completed successfully")
            else:
                self.append_output(f"\nBUILD FAILED (Exit code: {exit_code})")
                logger.warning(f"Build failed with exit code {exit_code}")

            self.build_in_progress = False
            self.cancel_button.setEnabled(False)
            self.close_button.setEnabled(True)
            self.cancel_button.clicked.disconnect()
            self.cancel_button.clicked.connect(self.close)
        except Exception as e:
            logger.error(f"Error in build_finished: {str(e)}", exc_info=True)

    def append_output(self, text: str):
        """Append text to the output widget."""
        try:
            self.output_text.append(text.strip())
            self.output_text.verticalScrollBar().setValue(
                self.output_text.verticalScrollBar().maximum()
            )
        except Exception as e:
            logger.error(f"Error updating GUI: {str(e)}", exc_info=True)

    def cancel_build(self):
        """Cancel the running build."""
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            try:
                self.append_output("\nCanceling build...")
                logger.info("Attempting to cancel build")
                self.process.terminate()  # Try graceful termination
                if not self.process.waitForFinished(5000):  # Wait 5 seconds
                    self.process.kill()  # Force kill if needed
                    self.append_output("Build process killed.")
                    logger.warning("Build process forcefully killed")
                else:
                    self.append_output("Build process terminated.")
                    logger.info("Build process terminated gracefully")
                self.builder.cleanup_build_artifacts()
            except Exception as e:
                self.append_output(f"Failed to cancel build: {str(e)}")
                logger.error(f"Cancel build failed: {str(e)}", exc_info=True)
        self.builder.build_in_progress = False
        self.build_finished(-1, QProcess.ExitStatus.CrashExit)

    def closeEvent(self, event):
        """Handle dialog closure."""
        if self.build_in_progress:
            self.cancel_build()
        if self.process:
            self.process.disconnect()  # Clean up signals
            self.process = None
        event.accept()