
import queue
import sys
import json
import os
import keyring
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QLabel,
    QMessageBox,
    QDialog,

)
from PyQt6.QtCore import Qt
from typing import Optional
from dialogs.connection_dialog import ConnectionSettingsDialog
from vcs.p4client import P4Client



class BuildBridgeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BuildBridge")
        self.setGeometry(100, 100, 400, 300)
        self.config_path = "vcsconfig.json"
        self.vcs_config = self.load_config()
        self.p4_client = P4Client(config=self.vcs_config)
        self.init_ui()

    def load_config(self):
        config = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    config = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Error decoding {self.config_path}: {e}")
            except Exception as e:
                print(f"Error loading {self.config_path}: {e}")

        if "perforce" in config and "config_override" in config["perforce"]:
            user = config["perforce"]["config_override"].get("p4user")
            if user:
                password = keyring.get_password("BuildBridge", user)
                if password:
                    config["perforce"]["config_override"]["p4password"] = password

        return config

    def save_config(self, new_config: dict):
        config_override = new_config["perforce"]["config_override"]
        user = config_override["p4user"]
        password = config_override["p4password"]
        if user and password:
            keyring.set_password("BuildBridge", user, password)

            # Load existing config to preserve other data
            current_config = {}
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    current_config = json.load(f)

            # Update with new config (excluding password)
            config_to_save = {
                "perforce": {
                    "config_override": {
                        k: v for k, v in config_override.items() if k != "p4password"
                    }
                }
            }
            current_config.update(config_to_save)

        # Save
        with open(self.config_path, "w") as f:
            json.dump(config_to_save, f, indent=4)

    def init_ui(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        settings_action = file_menu.addAction("Connection Settings")
        settings_action.triggered.connect(self.open_settings_dialog)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        layout.addWidget(QLabel("Release Branches:"))
        self.branch_list = QListWidget()
        layout.addWidget(self.branch_list)

        button_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh Branches")
        refresh_btn.clicked.connect(self.refresh_branches)
        button_layout.addWidget(refresh_btn)

        build_btn = QPushButton("Build Selected")
        build_btn.clicked.connect(self.trigger_build)
        button_layout.addWidget(build_btn)

        layout.addLayout(button_layout)
        self.refresh_branches()

    def open_settings_dialog(self):
        dialog = ConnectionSettingsDialog(self.vcs_config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_config = dialog.get_config()
            self.save_config(new_config)
            self.refresh_branches()

    def refresh_branches(self):
        try:
            self.branch_list.clear()
            branches = self.p4_client.get_branches()
            if not branches:
                self.branch_list.addItem("No release branches found.")
            else:
                self.branch_list.addItems(branches)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load branches: {str(e)}")

    def trigger_build(self):
        selected_items = self.branch_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(
                self, "Selection Error", "Please select a branch to build."
            )
            return
        selected_branch = selected_items[0].text()
        if selected_branch == "No release branches found.":
            QMessageBox.warning(self, "Selection Error", "No valid branch selected.")
            return
        try:
            self.p4_client.switch_to_ref(selected_branch)
            self.run_unreal_build(selected_branch)
            QMessageBox.information(
                self, "Build Started", f"Build triggered for {selected_branch}"
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Build Error", f"Failed to trigger build: {str(e)}"
            )

    def run_unreal_build(self, branch: str):
        print(f"Simulating Unreal build for branch: {branch}")

    def closeEvent(self, event):
        self.p4_client._disconnect()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    window = BuildBridgeWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
