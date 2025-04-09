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

import requests
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
        self._initial_username = "my-itch-username"
        self._initial_butler_path = ""
        # API Key field always starts blank

        # --- QProcess ---
        self.process: QProcess | None = None
        self._accumulated_output = ""

        # --- UI Elements ---
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("username")

        self.butler_path_input = QLineEdit()
        self.butler_path_input.setPlaceholderText("Path to butler executable")

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
        self.test_button.clicked.connect(self._test_connection)
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

        form_layout.addRow("Username", self.username_input)
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
                self._initial_username_input = ""
                self._initial_butler_path = ""
            else:
                # Ensure loaded object is in session
                if self.itch_config not in self.session:
                    self.session.add(self.itch_config)
                # Store initial values
                self._initial_username_input = self.itch_config.username or ""
                self._initial_butler_path = self.itch_config.butler_path or ""

            # Populate UI fields
            self.username_input.setText(self._initial_username_input)
            self.butler_path_input.setText(self._initial_butler_path)
            self.api_key_input.clear()  # Always clear API key field on load

            print(
                f"ItchConfigWidget: Loaded config. User/Game: {self._initial_username}"
            )
            self._reset_status_label()
            self.test_button.setEnabled(True)

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
            new_username = self.username_input.text().strip()
            new_butler_path = self.butler_path_input.text().strip()


            self.itch_config.username = new_username
            self.itch_config.butler_path = (
                new_butler_path if new_butler_path else None
            )  # Store None if empty

            # Update initial values
            self._initial_username = new_username
            self._initial_butler_path = new_butler_path

            # Handle API Key using the property setter (which uses keyring)
            entered_api_key = self.api_key_input.text()  # Don't strip API keys
            if entered_api_key:
                print(
                    "ItchConfigWidget: API Key field entered, attempting to store in keyring."
                )
                if not new_username:
                    raise ValueError("Cannot save API key without a Username.")
                self.itch_config.api_key = entered_api_key  # This calls the setter
            # else: If field is empty, the setter won't be called, existing key remains.

            self.api_key_input.clear()  # Clear field after handling  

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

    def _test_connection(self):
        """Tests connection using butler status with CURRENTLY ENTERED values."""
        print("ItchConfigWidget: Initiating connection test via butler...")

        api_key = self.api_key_input.text()  # Use value from field for test

        if not api_key:
            msg = "API Key field is empty for test. Connection test requires API Key."

            self._update_status_label(False, msg, QColor("orange"))
            QMessageBox.warning(self, "Input Error", msg)
            return
        
        result = requests.get(f"https://itch.io/api/1/{api_key}/credentials/info")
        if result.ok:
            self._update_status_label(True, message="Connection successful")
        else:
            self._update_status_label(False, message="Connection failed")
