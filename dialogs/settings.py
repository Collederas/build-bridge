import os
from typing import Dict, Tuple
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QStackedWidget,
    QFormLayout,
    QWidget,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QCheckBox,
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt

from vcs.p4client import P4Client
from app_config import ConfigManager


class SettingsDialog(QDialog):
    stores = ("Steam", "Epic")  # Now we support both Steam and Epic from ConfigManager

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(600, 400)

        # Initialize config managers
        self.vcs_config_manager = ConfigManager("vcs")
        self.stores_config_manager = ConfigManager("stores")

        # Load configs through managers
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout()

        self.category_list = QListWidget()
        self.category_list.addItems(["Version Control", "Publishing"])
        self.category_list.currentRowChanged.connect(self.switch_page)
        layout.addWidget(self.category_list, 1)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.create_vcs_page())
        self.stack.addWidget(self.create_publishing_page())
        layout.addWidget(self.stack, 3)

        button_layout = QHBoxLayout()
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self.apply_settings)
        button_layout.addWidget(apply_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

    def create_vcs_page(self):
        page = QWidget()
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # Get Perforce settings from ConfigManager
        p4port = self.vcs_config_manager.get("perforce.p4port", "")
        p4user = self.vcs_config_manager.get("perforce.p4user", "")
        p4client = self.vcs_config_manager.get("perforce.p4client", "")

        # Get password from keyring if user exists
        p4password = ""
        if p4user:
            p4password = self.vcs_config_manager.get_secure("BuildBridge", p4user) or ""

        self.p4user_input = QLineEdit(p4user)
        form_layout.addRow(QLabel("P4 User:"), self.p4user_input)

        self.p4password_input = QLineEdit(p4password)
        self.p4password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow(QLabel("P4 Password:"), self.p4password_input)

        self.p4port_input = QLineEdit(p4port)
        form_layout.addRow(QLabel("P4 Port:"), self.p4port_input)

        self.p4client_input = QLineEdit(p4client)
        form_layout.addRow(QLabel("P4 Client:"), self.p4client_input)

        layout.addLayout(form_layout)
        page.setLayout(layout)
        return page

    def create_publishing_page(self):
        page = QWidget()
        layout = QVBoxLayout()

        self.store_checkboxes = {}
        self.store_forms = {}

        for store_name in self.stores:
            store_key = store_name.lower()  # ConfigManager uses lowercase keys

            # Get store config from ConfigManager
            is_enabled = self.stores_config_manager.get(f"{store_key}.enabled", False)

            # Create checkbox for enabling the store
            checkbox = QCheckBox(f"Enable {store_name} Publishing")
            checkbox.setChecked(is_enabled)
            layout.addWidget(checkbox)
            self.store_checkboxes[store_name] = checkbox

            # Create form for store-specific settings
            form_widget = QWidget()
            form_layout = QFormLayout()

            if store_name == "Steam":
                # App ID field
                app_id = QLineEdit(
                    self.stores_config_manager.get(f"{store_key}.app_id", "")
                )
                form_layout.addRow(QLabel("App ID:"), app_id)

                # Username field
                username = QLineEdit(
                    self.stores_config_manager.get(f"{store_key}.username", "")
                )
                form_layout.addRow(QLabel("Username:"), username)

                # Description field
                description = QLineEdit(
                    self.stores_config_manager.get(
                        f"{store_key}.description", "My Game Build v1.0"
                    )
                )
                form_layout.addRow(QLabel("Description:"), description)

                # Depots field
                depot_ids = self.stores_config_manager.get(f"{store_key}.depots", [])
                depots = QTextEdit()
                depots.setPlainText("\n".join(depot_ids))
                depots.setFixedHeight(100)
                form_layout.addRow(QLabel("Depot IDs (one per line):"), depots)

                # Builder path field
                build_dir = os.getcwd()  # Default to current directory
                default_builder_path = os.path.normpath(
                    os.path.join(build_dir, "Steam/builder")
                )
                builder_path = QLineEdit(
                    self.stores_config_manager.get(
                        f"{store_key}.builder_path", default_builder_path
                    )
                )
                form_layout.addRow(QLabel("Builder Path:"), builder_path)

                # Browse button
                browse_btn = QPushButton("Browse")
                browse_btn.clicked.connect(
                    lambda _, p=builder_path: p.setText(
                        QFileDialog.getExistingDirectory(
                            self, "Select Builder Path", p.text()
                        )
                        or p.text()
                    )
                )
                form_layout.addRow("", browse_btn)

                # Store form fields for later access
                self.store_forms[store_name] = {
                    "app_id": app_id,
                    "username": username,
                    "description": description,
                    "depots": depots,
                    "builder_path": builder_path,
                }
            elif store_name == "Epic":
                # Add Epic-specific fields - based on the ConfigManager defaults
                product_id = QLineEdit(
                    self.stores_config_manager.get(f"{store_key}.product_id", "")
                )
                form_layout.addRow(QLabel("Product ID:"), product_id)

                artifact_id = QLineEdit(
                    self.stores_config_manager.get(f"{store_key}.artifact_id", "")
                )
                form_layout.addRow(QLabel("Artifact ID:"), artifact_id)

                self.store_forms[store_name] = {
                    "product_id": product_id,
                    "artifact_id": artifact_id,
                }

            form_widget.setLayout(form_layout)
            form_widget.setVisible(is_enabled)

            # Connect checkbox to toggle form visibility
            checkbox.stateChanged.connect(
                lambda state, w=form_widget: w.setVisible(
                    state == Qt.CheckState.Checked.value
                )
            )

            layout.addWidget(form_widget)

        layout.addStretch()
        page.setLayout(layout)
        return page

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)

    def save_vcs_settings(self) -> bool:
        """Save VCS settings and verify connection."""
        
        # Get user and password
        user = self.p4user_input.text().strip()
        password = self.p4password_input.text().strip()
        client = self.p4client_input.text().strip()
        port = self.p4port_input.text().strip()

        self.vcs_config_manager.set("perforce.p4user", user)
        self.vcs_config_manager.set("perforce.p4client", client)
        self.vcs_config_manager.set("perforce.p4port", port)
        self.vcs_config_manager.set_secure("BuildBridge", user, password)

        # Try to establish connection with the new settings
        try:
            # Test connection
            P4Client()

            # Save settings to file
            self.vcs_config_manager.save()
            return True

        except ConnectionError:
            QMessageBox.critical(
                self,
                "Connection Error",
                "Connection Error. Check your Perforce connection settings and retry.",
            )
        return False

    def save_store_settings(self):
        """Save store settings."""
        for store_name, checkbox in self.store_checkboxes.items():
            store_key = store_name.lower()
            is_enabled = checkbox.isChecked()

            # Set enabled state in config
            self.stores_config_manager.set(f"{store_key}.enabled", is_enabled)

            # Handle specific store types
            if store_name == "Steam" and store_name in self.store_forms:
                form = self.store_forms[store_name]

                # Get depot IDs from text input
                depot_text = form["depots"].toPlainText().strip()
                depot_ids = [d.strip() for d in depot_text.split("\n") if d.strip()]

                # Update store config
                self.stores_config_manager.set(
                    f"{store_key}.app_id", form["app_id"].text().strip()
                )
                self.stores_config_manager.set(
                    f"{store_key}.username", form["username"].text().strip()
                )
                self.stores_config_manager.set(
                    f"{store_key}.description", form["description"].text().strip()
                )
                self.stores_config_manager.set(f"{store_key}.depots", depot_ids)
                self.stores_config_manager.set(
                    f"{store_key}.builder_path", form["builder_path"].text().strip()
                )

            elif store_name == "Epic" and store_name in self.store_forms:
                form = self.store_forms[store_name]
                self.stores_config_manager.set(
                    f"{store_key}.product_id", form["product_id"].text().strip()
                )
                self.stores_config_manager.set(
                    f"{store_key}.artifact_id", form["artifact_id"].text().strip()
                )

        # Save all store settings
        self.stores_config_manager.save()

    def apply_settings(self):
        # Save VCS settings and verify connection
        vcs_saved = self.save_vcs_settings()

        # Save store settings
        self.save_store_settings()

        # Only accept if VCS connection was successful
        if vcs_saved:
            self.accept()

    def get_configs(self) -> Tuple[Dict, Dict]:
        """Get the current configs (for backward compatibility)."""
        vcs_config = {
            "perforce": {
                "p4user": self.vcs_config_manager.get("perforce.p4user", ""),
                "p4client": self.vcs_config_manager.get("perforce.p4client", ""),
                "p4port": self.vcs_config_manager.get("perforce.p4port", ""),
            }
        }

        # Format stores config to match expected output structure
        store_configs = {
            "configs": [{}],
        }

        # Add Steam config if available
        if "Steam" in self.store_forms:
            steam_key = "Steam"
            store_configs["configs"][steam_key] = {
                "enabled": self.stores_config_manager.get("steam.enabled", False),
                "app_id": self.stores_config_manager.get("steam.app_id", ""),
                "username": self.stores_config_manager.get("steam.username", ""),
                "description": self.stores_config_manager.get(
                    "steam.description", "My Game Build v1.0"
                ),
                "depots": self.stores_config_manager.get("steam.depots", []),
                "builder_path": self.stores_config_manager.get(
                    "steam.builder_path", ""
                ),
            }

        # Add Epic config if available
        if "Epic" in self.store_forms:
            epic_key = "Epic"
            store_configs["configs"][epic_key] = {
                "enabled": self.stores_config_manager.get("epic.enabled", False),
                "product_id": self.stores_config_manager.get("epic.product_id", ""),
                "artifact_id": self.stores_config_manager.get("epic.artifact_id", ""),
            }
        
        print(store_configs)

        return vcs_config, store_configs
