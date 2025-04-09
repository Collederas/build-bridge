from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QFormLayout, QMessageBox, QApplication, QFileDialog
)
from PyQt6.QtCore import QProcess

from sqlalchemy.orm import Session
from models import SteamConfig

class SteamConfigWidget(QWidget):
    """
    Manages the single Steam configuration (paths, username, password).
    Provides a button to test the connection using steamcmd.

    !! The login method passes passwords on the command line, which
    is generally insecure !!
    
    CAVEAT: Does not handle Steam Guard (2FA) prompts automatically.
    """

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self.steam_config: SteamConfig | None = None

        # --- Internal State ---
        # Store initial loaded values for reset capability
        self._initial_username = ""
        self._initial_steamcmd_path = ""
        # Password field always starts blank, no initial value needed in UI

        # --- QProcess ---
        self.process: QProcess | None = None
        self._accumulated_output = ""

        # --- UI Elements ---
        # Configuration Inputs
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Enter password to set/change")

        self.steamcmd_path_input = QLineEdit()

        steamcmd_browse_button = QPushButton("Browse...")
        steamcmd_browse_button.clicked.connect(lambda: self._browse_file(self.steamcmd_path_input, "Select SteamCMD Executable"))

        # Test Button
        self.test_button = QPushButton("Test Connection")
        self.test_button.clicked.connect(self._test_connection_with_steamcmd)
        self.test_button.setMinimumWidth(150)

        # Status Label
        self.status_label = QLabel("Status: Not tested yet.")
        font = self.status_label.font()
        font.setPointSize(10) # Standard size might be fine
        font.setItalic(True)
        self.status_label.setFont(font)
        self.status_label.setStyleSheet("color: gray;") # Initial style

        # --- Layout ---
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        form_layout.addRow("Username:", self.username_input)
        form_layout.addRow("Password:", self.password_input)

        # SteamCMD Path with Browse
        steamcmd_layout = QHBoxLayout()
        steamcmd_layout.addWidget(self.steamcmd_path_input)
        steamcmd_layout.addWidget(steamcmd_browse_button)
        form_layout.addRow("SteamCMD Path:", steamcmd_layout)

        main_layout.addLayout(form_layout)
        main_layout.addSpacing(15)
        # Place button and status label together
        test_layout = QHBoxLayout()
        test_layout.addWidget(self.status_label, 1) # Label takes available space
        test_layout.addStretch()
        test_layout.addWidget(self.test_button)
        main_layout.addLayout(test_layout)

        main_layout.addStretch() # Push content to top

        # --- Initialization ---
        self.load_settings()

    # --- File/Directory Browse ---
    def _browse_file(self, line_edit: QLineEdit, title: str):
        # Adjust filter as needed, e.g., "Executables (*.exe)" on Windows
        file_path, _ = QFileDialog.getOpenFileName(self, title, line_edit.text())
        if file_path:
            line_edit.setText(file_path)

    def _browse_directory(self, line_edit: QLineEdit, title: str):
        folder = QFileDialog.getExistingDirectory(self, title, line_edit.text())
        if folder:
            line_edit.setText(folder)

    # --- SettingsDialog Integration Methods ---

    def load_settings(self):
        """Loads configuration into the input fields."""
        print("SteamConfigWidget: Loading settings...")
        try:
            # Query for the single config entry, create if doesn't exist
            self.steam_config = self.session.query(SteamConfig).first()
            if not self.steam_config:
                print("SteamConfigWidget: No config found, creating new one in session.")
                self.steam_config = SteamConfig()
                self._initial_username = ""
                self._initial_steamcmd_path = ""
            else:
                 if self.steam_config not in self.session:
                     self.session.add(self.steam_config)
                 # Store initial values from loaded config
                 self._initial_username = self.steam_config.username or ""
                 self._initial_steamcmd_path = self.steam_config.steamcmd_path or ""

            # Populate UI fields from initial values (or defaults if new)
            self.username_input.setText(self._initial_username)
            self.steamcmd_path_input.setText(self._initial_steamcmd_path)
            self.password_input.clear() # Always clear password field on load

            print(f"SteamConfigWidget: Loaded config. User: {self._initial_username}")
            self._reset_status_label()

        except Exception as e:
            print(f"SteamConfigWidget: Error loading settings: {e}")
            self.status_label.setText(f"Error loading config: {e}")
            self.status_label.setStyleSheet("color: red; font-style: normal;")
            # Disable inputs/button on load error?
            self.test_button.setEnabled(False)
            self.username_input.setEnabled(False)
            # ... disable others

    def save_settings(self):
        """Saves current values from input fields into the config object."""

        # IMPORTANT: No commit here! SettingsDialog handles the commit.

        if not self.steam_config:
            print("SteamConfigWidget: Cannot save, config object missing.")
            raise Exception("Steam configuration object not found during save.")
        
        if self.steam_config not in self.session:
           print(f"  *** Adding self.steam_config object to session NOW! ***")
           self.session.add(self.steam_config)

        
        print("SteamConfigWidget: Preparing settings for save...")
        try:
            # --- Update config object from UI fields ---
            new_username = self.username_input.text().strip()
            new_steamcmd_path = self.steamcmd_path_input.text().strip()

            self.steam_config.username = new_username
            self.steam_config.steamcmd_path = new_steamcmd_path

            # Update initial values to reflect saved state
            self._initial_username = new_username
            self._initial_steamcmd_path = new_steamcmd_path

            # --- Handle Password ---
            entered_password = self.password_input.text()
            if entered_password:
                 print("SteamConfigWidget: Password field entered, updating stored password (INSECURE if saving to DB).")
                 self.steam_config.password = entered_password
            else:
                 # If field is empty, DO NOT overwrite existing stored password
                 print("SteamConfigWidget: Password field empty, stored password remains unchanged.")

            self.password_input.clear() # Clear password field after handling


        except Exception as e:
            print(f"SteamConfigWidget: Error preparing settings for save: {e}")
            raise Exception(f"Failed to stage Steam settings for saving: {e}") from e

    def reset_to_initial_state(self):
        """Resets input fields to their initially loaded values."""
        print("SteamConfigWidget: Resetting UI to initial state...")
        self.username_input.setText(self._initial_username)
        self.steamcmd_path_input.setText(self._initial_steamcmd_path)
        self.password_input.clear()
        self._reset_status_label()

    def _update_status_label(self, success: bool, message: str):
        """ Updates the status label with appropriate color and text. """
        self.status_label.setText(f"Status: {message}")
        if success:
            self.status_label.setStyleSheet("color: green; font-style: normal;")
        else:
            # Use red for errors, gray for inconclusive/untested
            color = "red" if "failed" in message.lower() or "error" in message.lower() else "gray"
            self.status_label.setStyleSheet(f"color: {color}; font-style: normal;")

    def _reset_status_label(self):
        """ Helper to reset the status label """
        self.status_label.setText("Status: Not tested yet.")
        self.status_label.setStyleSheet("color: gray; font-style: italic;")

    def _test_connection_with_steamcmd(self):
        """Tests connection using steamcmd with CURRENTLY ENTERED values."""
        print("SteamConfigWidget: Initiating connection test via steamcmd...")

        # --- Get values DIRECTLY from input fields for testing ---
        steamcmd_path = self.steamcmd_path_input.text().strip()
        username = self.username_input.text().strip()
        # Get password ONLY if entered, otherwise treat as empty string for command
        password = self.password_input.text() # Use password from field for test

        if not steamcmd_path or not username:
            msg = "SteamCMD path or username field is empty."
            self._update_status_label(False, msg) # Update status label immediately
            QMessageBox.warning(self, "Input Error", msg)
            return

        # Optional: Warn if password field is empty but maybe expected
        if not password:
             print("SteamConfigWidget: Password field empty for test. SteamCMD might prompt if required.")
        else:
             print("SteamConfigWidget: SECURITY WARNING - Using password from input field for command line (insecure).")


        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            print("SteamConfigWidget: Test process already running.")
            QMessageBox.information(self, "Busy", "A connection test is already in progress.")
            return

        # --- Prepare and Start QProcess ---
        self.test_button.setEnabled(False) # Disable button during test
        self.status_label.setText("Status: Testing connection...")
        self.status_label.setStyleSheet("color: orange; font-style: normal;")
        QApplication.processEvents() # Ensure UI updates immediately

        self._accumulated_output = "" # Reset output for this run

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._handle_test_output)
        self.process.finished.connect(self._handle_test_finished)
        self.process.errorOccurred.connect(self._handle_test_error)

        # Assemble command using values from input fields
        command_exe = steamcmd_path
        command_args = ["+login", username]
        if password:
            command_args.append(password)
        command_args.append("+quit")

        print(f"SteamConfigWidget: Starting test process: {command_exe} {' '.join(command_args[:2])} ***** +quit")

        self.process.start(command_exe, command_args)


    # --- QProcess Signal Handlers for Testing ---

    def _handle_test_output(self):
        """Reads and accumulates merged output from the test process."""
        if not self.process: return
        try:
            output_bytes = self.process.readAllStandardOutput()
            output_string = output_bytes.data().decode(errors='ignore').strip()
            if output_string:
                print(f"SteamCMD Test Output: {output_string}")
                self._accumulated_output += output_string + "\n"
        except Exception as e:
            print(f"Error reading test process output: {e}")


    def _handle_test_error(self, error: QProcess.ProcessError):
        """Handles errors in starting/running the QProcess itself during test."""
        if not self.process: return
        print(f"SteamConfigWidget: QProcess error occurred during test: {error}")
        error_map = { ... } # Same map as before
        error_msg = f"Process error: {error_map.get(error, 'Unknown')}"
        self._update_status_label(False, error_msg)
        self.test_button.setEnabled(True) # Re-enable button on process error
        self.process = None


    def _handle_test_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        """Handles the completion of the test QProcess."""
        if self.process is None: return
        print(f"SteamConfigWidget: Test process finished. ExitCode: {exit_code}, ExitStatus: {exit_status}")

        success = False
        message = ""
        full_output = self._accumulated_output.lower()

        if exit_status == QProcess.ExitStatus.CrashExit:
            message = "SteamCMD process crashed during test."
        elif exit_code != 0:
            message = f"SteamCMD exited with error code {exit_code}."
            # Check common failure reasons in output
            if "invalid password" in full_output:
                 message = "Connection failed: Invalid password."
            elif "steam guard" in full_output:
                 message = "Connection failed: Steam Guard code required (not supported)."
            elif self._accumulated_output:
                 message += f"\nDetails:\n{self._accumulated_output.strip()}"
        elif "error!" in full_output or "failed" in full_output:
             message = "SteamCMD reported errors during test."
             if "invalid password" in full_output:
                  message = "Connection failed: Invalid password reported."
             elif "steam guard" in full_output:
                  message = "Connection failed: Steam Guard code required (not supported)."
             else:
                  message += f"\nDetails:\n{self._accumulated_output.strip()}"
        else:
             # Exit code 0, normal exit, no obvious errors detected
             # Treat this as a successful connection test for the purpose of the UI
             print("SteamConfigWidget: Test finished successfully.")
             success = True
             message = "Connection successful!"

        # Update status label and re-enable button
        self._update_status_label(success, message)
        self.test_button.setEnabled(True)
        self.process = None # Clean up

        # Optional: Show message box on failure
        if not success:
            QMessageBox.warning(self, "Connection Test Failed", message)

    def cleanup(self):
        """Kills any running QProcess."""
        print(f"{self.__class__.__name__}: Running cleanup...")
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            print(f"{self.__class__.__name__}: Terminating running test process...")
            self.process.kill() # Force kill steamcmd
            if not self.process.waitForFinished(1000): # Wait briefly
                 print(f"{self.__class__.__name__}: Process did not finish after kill signal.")
            self.process = None
            print(f"{self.__class__.__name__}: Process terminated.")
        else:
            print(f"{self.__class__.__name__}: No active process found.")   
 