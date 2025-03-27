import multiprocessing
import queue
import sys
import json
import os
import keyring
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QLabel, QMessageBox, QDialog, QFormLayout,
    QLineEdit, QDialogButtonBox
)
from PyQt6.QtCore import Qt
from typing import Optional
from vcs.p4client import P4Client

def connect_in_process(vcs_type, port: str, user: str, password: str, client: str, result_queue: multiprocessing.Queue):
    """Run connection test in a separate process using the specified VCS type."""
    result, error_msg = vcs_type.test_connection(port, user, password, client)
    result_queue.put((result, error_msg))

class ConnectionSettingsDialog(QDialog):
    def __init__(self, current_config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Perforce Connection Settings")
        self.current_config = current_config.get("perforce", {}).get("config_override", {})
        self.has_existing_config = bool(self.current_config)
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self)

        self.port_input = QLineEdit(self.current_config.get("p4port", ""))
        self.user_input = QLineEdit(self.current_config.get("p4user", ""))
        self.password_input = QLineEdit(self.current_config.get("p4password", ""))
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.client_input = QLineEdit(self.current_config.get("p4client", ""))

        layout.addRow("Port:", self.port_input)
        layout.addRow("User:", self.user_input)
        layout.addRow("Password:", self.password_input)
        layout.addRow("Client:", self.client_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        test_button = QPushButton("Test Connection")
        test_button.clicked.connect(self.test_connection)

        layout.addWidget(test_button)
        layout.addWidget(buttons)

        if self.has_existing_config:
            layout.insertRow(0, QLabel("Editing existing connection settings:"))

    def test_connection(self):
        result_queue = multiprocessing.Queue()
        port = self.port_input.text()
        user = self.user_input.text()
        password = self.password_input.text()
        client = self.client_input.text()

        process = multiprocessing.Process(
            target=connect_in_process,
            args=(P4Client, port, user, password, client, result_queue)
        )
        process.start()
        process.join(timeout=5)

        if process.is_alive():
            process.terminate()
            process.join()
            QMessageBox.critical(self, "Connection Test", "Connection timed out: Server not responding.")
        else:
            if not result_queue.empty():
                result, error_msg = result_queue.get()
                if result == "success":
                    QMessageBox.information(self, "Connection Test", "Connection successful!")
                else:
                    QMessageBox.critical(self, "Connection Test", f"Connection failed: {error_msg}")
            else:
                QMessageBox.critical(self, "Connection Test", "Connection failed: No response from process.")

    def get_config(self):
        return {
            "perforce": {
                "config_override": {
                    "p4port": self.port_input.text(),
                    "p4user": self.user_input.text(),
                    "p4password": self.password_input.text(),
                    "p4client": self.client_input.text()
                }
            }
        }

class BuildBridgeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BuildBridge")
        self.setGeometry(100, 100, 400, 300)
        self.config_path = "vcsconfig.json"
        self.load_config()
        self.p4_client = P4Client(config=self.config)
        self.init_ui()

    def load_config(self):
        self.config = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    self.config = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Error decoding {self.config_path}: {e}")
            except Exception as e:
                print(f"Error loading {self.config_path}: {e}")
        if "perforce" in self.config and "config_override" in self.config["perforce"]:
            user = self.config["perforce"]["config_override"].get("p4user")
            if user:
                password = keyring.get_password("BuildBridge", user)
                if password:
                    self.config["perforce"]["config_override"]["p4password"] = password

    def save_config(self, new_config: dict):
        config_override = new_config["perforce"]["config_override"]
        user = config_override["p4user"]
        password = config_override["p4password"]
        if user and password:
            keyring.set_password("BuildBridge", user, password)

        config_to_save = {
            "perforce": {
                "config_override": {k: v for k, v in config_override.items() if k != "p4password"}
            }
        }
        with open(self.config_path, "w") as f:
            json.dump(config_to_save, f, indent=4)

        self.config = new_config
        self.p4_client = P4Client(config=self.config)

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
        dialog = ConnectionSettingsDialog(self.config, self)
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
            QMessageBox.warning(self, "Selection Error", "Please select a branch to build.")
            return
        selected_branch = selected_items[0].text()
        if selected_branch == "No release branches found.":
            QMessageBox.warning(self, "Selection Error", "No valid branch selected.")
            return
        try:
            self.p4_client.switch_to_ref(selected_branch)
            self.run_unreal_build(selected_branch)
            QMessageBox.information(self, "Build Started", f"Build triggered for {selected_branch}")
        except Exception as e:
            QMessageBox.critical(self, "Build Error", f"Failed to trigger build: {str(e)}")

    def run_unreal_build(self, branch: str):
        print(f"Simulating Unreal build for branch: {branch}")

    def closeEvent(self, event):
        self.p4_client.disconnect()
        super().closeEvent(event)

def main():
    app = QApplication(sys.argv)
    window = BuildBridgeWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()