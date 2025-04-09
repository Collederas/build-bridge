import os
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QFormLayout,
    QMessageBox,
    QApplication,
    QFileDialog,
)
from PyQt6.QtCore import QProcess, QProcessEnvironment
from PyQt6.QtGui import QColor

from sqlalchemy.orm import Session

from models import ItchConfig


class ItchConfigWidget(QWidget):
    """
    Manages the Itch.io configuration (User/Game ID, Butler Path, API Key).
    Provides a button to test the connection using butler.
    """

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self.itch_config: ItchConfig | None = None

        # --- Internal State ---
        self._initial_user_game_id = ""
        self._initial_butler_path = ""
        # API Key field always starts blank

        # --- QProcess ---
        self.process: QProcess | None = None
        self._accumulated_output = ""

        # --- UI Elements ---
        self.user_game_id_input = QLineEdit()
        self.user_game_id_input.setPlaceholderText("username/game-url-name")

        self.butler_path_input = QLineEdit()
        self.butler_path_input.setPlaceholderText("Optional: Path to butler executable")

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText(
            "Enter API Key to set/change (uses system keyring)"
        )

        butler_browse_button = QPushButton("Browse...")
        butler_browse_button.clicked.connect(
            lambda: self._browse_file(
                self.butler_path_input, "Select Butler Executable"
            )
        )

        self.test_button = QPushButton("Test Connection")
        self.test_button.clicked.connect(self._test_connection_with_butler)
        self.test_button.setMinimumWidth(150)

        self.status_label = QLabel("Status: Not tested yet.")
        font = self.status_label.font()
        font.setItalic(True)
        self.status_label.setFont(font)
        self.status_label.setStyleSheet("color: gray;")

        # --- Layout ---
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        form_layout.addRow("User/Game ID:", self.user_game_id_input)
        form_layout.addRow("API Key:", self.api_key_input)

        butler_path_layout = QHBoxLayout()
        butler_path_layout.addWidget(self.butler_path_input)
        butler_path_layout.addWidget(butler_browse_button)
        form_layout.addRow("Butler Path:", butler_path_layout)

        # Note about keyring usage
        keyring_note = QLabel(
            "Note: The API Key is securely stored using the system keyring."
        )
        keyring_note.setWordWrap(True)
        keyring_note.setStyleSheet("font-style: italic; color: gray; font-size: 9pt;")
        form_layout.addRow("", keyring_note)

        main_layout.addLayout(form_layout)
        main_layout.addSpacing(15)

        test_layout = QHBoxLayout()
        test_layout.addWidget(self.status_label, 1)
        test_layout.addStretch()
        test_layout.addWidget(self.test_button)
        main_layout.addLayout(test_layout)

        main_layout.addStretch()

        # --- Initialization ---
        self.load_settings()

    # --- Browse Functionality ---
    def _browse_file(self, line_edit: QLineEdit, title: str):
        # Consider adding executable filters based on OS
        file_path, _ = QFileDialog.getOpenFileName(self, title, line_edit.text())
        if file_path:
            line_edit.setText(file_path)

    # --- SettingsDialog Integration Methods ---
    def load_settings(self):
        """Loads Itch.io configuration into the input fields."""
        print("ItchConfigWidget: Loading settings...")
        try:
            # Query or create the single config entry
            self.itch_config = self.session.query(ItchConfig).first()
            if not self.itch_config:
                print("ItchConfigWidget: No config found, creating new one in session.")
                self.itch_config = ItchConfig()
                self.session.add(self.itch_config)  # Add to session NOW
                self._initial_user_game_id = ""
                self._initial_butler_path = ""
            else:
                # Ensure loaded object is in session
                if self.itch_config not in self.session:
                    self.session.add(self.itch_config)
                # Store initial values
                self._initial_user_game_id = self.itch_config.itch_user_game_id or ""
                self._initial_butler_path = self.itch_config.butler_path or ""

            # Populate UI fields
            self.user_game_id_input.setText(self._initial_user_game_id)
            self.butler_path_input.setText(self._initial_butler_path)
            self.api_key_input.clear()  # Always clear API key field on load

            print(
                f"ItchConfigWidget: Loaded config. User/Game: {self._initial_user_game_id}"
            )
            self._reset_status_label()
            self.test_button.setEnabled(
                bool(self._initial_user_game_id)
            )  # Enable test only if ID is set

        except Exception as e:
            print(f"ItchConfigWidget: Error loading settings: {e}")
            self.status_label.setText(f"Error loading config: {e}")
            self.status_label.setStyleSheet("color: red; font-style: normal;")
            self.test_button.setEnabled(False)
            # Disable inputs?

    def save_settings(self):
        """Saves current values into the config object (without committing)."""
        if not self.itch_config:
            print("ItchConfigWidget: Cannot save, config object missing.")
            raise RuntimeError("Itch configuration object not found during save.")

        # Ensure object is still in session (important if dialog is reused)
        if self.itch_config not in self.session:
            print(
                "ItchConfigWidget: Warning - ItchConfig object was not in session during save. Re-adding."
            )
            self.session.add(self.itch_config)

        print("ItchConfigWidget: Preparing settings for save...")
        try:
            # Update config object from UI fields
            new_user_game_id = self.user_game_id_input.text().strip()
            new_butler_path = self.butler_path_input.text().strip()

            # Validate format before assigning
            if new_user_game_id and "/" not in new_user_game_id:
                raise ValueError("User/Game ID must be in 'username/game-name' format.")

            self.itch_config.itch_user_game_id = new_user_game_id
            self.itch_config.butler_path = (
                new_butler_path if new_butler_path else None
            )  # Store None if empty

            # Update initial values
            self._initial_user_game_id = new_user_game_id
            self._initial_butler_path = new_butler_path

            # Handle API Key using the property setter (which uses keyring)
            entered_api_key = self.api_key_input.text()  # Don't strip API keys
            if entered_api_key:
                print(
                    "ItchConfigWidget: API Key field entered, attempting to store in keyring."
                )
                # The setter requires user_game_id to be set first
                if not new_user_game_id:
                    raise ValueError("Cannot save API key without a User/Game ID.")
                self.itch_config.api_key = entered_api_key  # This calls the setter
            # else: If field is empty, the setter won't be called, existing key remains.

            self.api_key_input.clear()  # Clear field after handling
            self.test_button.setEnabled(
                bool(new_user_game_id)
            )  # Update test button state

        except Exception as e:
            print(f"ItchConfigWidget: Error preparing settings for save: {e}")
            # Rollback might happen in SettingsDialog, but good practice to raise
            raise  # Re-raise the exception to be caught by SettingsDialog

    # --- Status Label Helpers ---
    def _update_status_label(self, success: bool, message: str, color: QColor = None):
        self.status_label.setText(f"Status: {message}")
        if color:
            style_color = color.name()
        else:
            style_color = "green" if success else "red"
        self.status_label.setStyleSheet(f"color: {style_color}; font-style: normal;")

    def _reset_status_label(self):
        self.status_label.setText("Status: Not tested yet.")
        self.status_label.setStyleSheet("color: gray; font-style: italic;")

    # --- Butler Test Connection ---
    def _test_connection_with_butler(self):
        """Tests connection using butler status with CURRENTLY ENTERED values."""
        print("ItchConfigWidget: Initiating connection test via butler...")

        butler_exe = self.butler_path_input.text().strip() or "butler"
        user_game_id = self.user_game_id_input.text().strip()
        api_key = self.api_key_input.text()  # Use value from field for test

        if not user_game_id:
            msg = "User/Game ID field is empty."
            self._update_status_label(False, msg, QColor("orange"))
            QMessageBox.warning(self, "Input Error", msg)
            return

        if not api_key:
            msg = "API Key field is empty for test. Connection test requires API Key."
            # Alternative: Try running without API key if butler allows testing login status differently?
            # For now, require API key for test via environment variable.
            self._update_status_label(False, msg, QColor("orange"))
            QMessageBox.warning(self, "Input Error", msg)
            return

        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            QMessageBox.information(
                self, "Busy", "A connection test is already in progress."
            )
            return

        # --- Prepare and Start QProcess ---
        self.test_button.setEnabled(False)
        self.status_label.setText("Status: Testing connection...")
        self.status_label.setStyleSheet("color: orange; font-style: normal;")
        QApplication.processEvents()

        self._accumulated_output = ""

        self.process = QProcess(self)

        process_env = QProcessEnvironment.systemEnvironment()
        process_env.insert("BUTLER_API_KEY", f"{api_key}")
        process_env.insert("BUTLER_NO_TTY", "1")

        self.process.setProcessEnvironment(process_env)

        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._handle_test_output)
        self.process.finished.connect(self._handle_test_finished)
        self.process.errorOccurred.connect(self._handle_test_error)

        # Use 'butler status' command for testing
        command_args = ["status", user_game_id]

        print(
            f"ItchConfigWidget: Starting test process: {butler_exe} {' '.join(command_args)}"
        )
        try:
            self.process.start(butler_exe, command_args)
            if not self.process.waitForStarted(3000):
                raise RuntimeError(
                    f"Failed to start butler process: {self.process.errorString()}"
                )
        except Exception as e:
            print(f"Error starting test process: {e}")
            self._handle_test_error(
                QProcess.ProcessError.FailedToStart
            )  # Simulate error signal

    # --- QProcess Signal Handlers for Testing ---
    def _handle_test_output(self):
        if not self.process:
            return
        try:
            output_bytes = self.process.readAllStandardOutput()
            output_string = output_bytes.data().decode(errors="replace").strip()
            if output_string:
                print(f"Butler Test Output: {output_string}")
                self._accumulated_output += output_string + "\n"
        except Exception as e:
            print(f"Error reading test process output: {e}")

    def _handle_test_error(self, error: QProcess.ProcessError):
        if not self.process:
            return
        print(f"ItchConfigWidget: QProcess error occurred during test: {error}")
        error_map = {
            QProcess.ProcessError.FailedToStart: "Failed to start butler.",
            # Add other QProcess errors as needed
        }
        error_msg = f"Process error: {error_map.get(error, 'Unknown')}"
        self._update_status_label(False, error_msg)
        self.test_button.setEnabled(True)
        self.process = None

    def _handle_test_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        if self.process is None:
            return
        print(
            f"ItchConfigWidget: Test process finished. ExitCode: {exit_code}, ExitStatus: {exit_status}"
        )

        success = False
        message = ""
        full_output = self._accumulated_output.lower()

        if exit_status == QProcess.ExitStatus.CrashExit:
            message = "Butler process crashed during test."
        elif exit_code != 0:
            message = f"Butler exited with error code {exit_code}."
            if "invalid api key" in full_output or "denied" in full_output:
                message = "Connection failed: Invalid API Key or access denied."
            elif "unregistered game" in full_output or "not found" in full_output:
                message = "Connection failed: User/Game ID not found or incorrect."
            elif self._accumulated_output:
                message += f" Details: {self._accumulated_output.strip()}"
        elif "error" in full_output or "fail" in full_output:
            message = "Butler reported errors during test."
            # Add more specific parsing if needed
            message += f" Details: {self._accumulated_output.strip()}"
        else:
            # Exit code 0, normal exit, no obvious errors detected
            print("ItchConfigWidget: Test finished successfully.")
            success = True
            message = "Connection successful!"

        self._update_status_label(success, message)
        self.test_button.setEnabled(True)
        self.process = None

        if not success:
            QMessageBox.warning(self, "Connection Test Failed", message)

    def cleanup(self):
        """Kills any running test QProcess."""
        print(f"{self.__class__.__name__}: Running cleanup...")
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            print(f"{self.__class__.__name__}: Terminating running test process...")
            self.process.kill()
            self.process.waitForFinished(500)
            self.process = None
            print(f"{self.__class__.__name__}: Test process terminated.")
        else:
            print(f"{self.__class__.__name__}: No active test process found.")
