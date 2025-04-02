import os
import subprocess
import keyring
import logging
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QLabel,
    QTextEdit,
    QMessageBox,
    QWizard,
)
from PyQt6.QtCore import QThread, pyqtSignal
from publisher.base_publisher import BasePublisher
from publisher.steam.steam_wizard import SteamBuildSetupWizard

logger = logging.getLogger(__name__)


class SteamConfigDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Steam Configuration")
        self.config = config
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        self.app_id_input = QLineEdit(self.config.get("app_id", ""))
        form_layout.addRow(QLabel("Steam App ID:"), self.app_id_input)

        self.username_input = QLineEdit(self.config.get("username", ""))
        form_layout.addRow(QLabel("Steam Username:"), self.username_input)

        self.password_input = QLineEdit(self.config.get("password", ""))
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow(QLabel("Steam Password:"), self.password_input)

        layout.addLayout(form_layout)

        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        button_layout.addWidget(save_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def validate_config(self):
        config = self.get_config()
        if config["app_id"] and config["username"]:
            return True
        else:
            QMessageBox.warning(
                self, "Input Error", "App ID and username are required."
            )
            return False

    def accept(self):
        if self.validate_config():
            super().accept()

    def get_config(self):
        return {
            "app_id": self.app_id_input.text().strip(),
            "username": self.username_input.text().strip(),
            "password": self.password_input.text().strip(),
        }


class UploadThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self, steamcmd_path, builder_path, config):
        super().__init__()
        self.steamcmd_path = steamcmd_path
        self.build_path = builder_path
        self.config = config

    def run(self):
        try:
            cmd = [
                self.steamcmd_path,
                "+login",
                self.config["username"],
                self.config["password"],
                "+app_build",
                self.build_path,  # Assumes a VDF file exists
                "+quit",
            ]
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    self.log_signal.emit(line.strip())
            success = process.returncode == 0
            if not success:
                errors = process.stderr.read()
                self.log_signal.emit(f"Error: {errors}")
            self.finished_signal.emit(success)
        except Exception as e:
            self.log_signal.emit(f"Upload failed: {str(e)}")
            self.finished_signal.emit(False)


class SteamUploadDialog(QDialog):
    def __init__(self, builder_path, config, steamcmd_path="C:/steamcmd/steamcmd.exe", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Upload to Steam")

        self.vdf_file = os.path.join(builder_path, "app_build.vdf")

        self.config = config
        self.steamcmd_path = steamcmd_path
        self.setup_ui()
        self.start_upload()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel(f"Uploading: {self.vdf_file}"))
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        layout.addWidget(self.log_display)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        layout.addWidget(self.cancel_btn)
        self.setLayout(layout)

    def start_upload(self):
        self.thread = UploadThread(self.steamcmd_path, self.vdf_file, self.config)
        self.thread.log_signal.connect(self.update_log)
        self.thread.finished_signal.connect(self.upload_finished)
        self.thread.start()

    def update_log(self, text):
        self.log_display.append(text)
        logger.info(text)

    def upload_finished(self, success):
        self.cancel_btn.setText("Close")
        if success:
            self.log_display.append("Upload completed successfully!")
        else:
            self.log_display.append("Upload failed. Check logs for details.")


class SteamPublisher(BasePublisher):
    store_name = "Steam"

    def __init__(self, build_path, config_path="steam_config.json"):
        super().__init__(build_path, config_path)

        # Houses the .vdf files
        self.builder_path = os.path.join(self.store_config_dir, "builder")

        self.username = self.config.get("username", "")
        if self.username:
            self.config["password"] = (
                keyring.get_password("BuildBridgeSteam", self.username) or ""
            )

    def configure(self, parent=None):
        dialog = SteamConfigDialog(self.config, parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_config = dialog.get_config()
            if new_config["password"]:
                keyring.set_password(
                    "BuildBridgeSteam", new_config["username"], new_config["password"]
                )
            self.save_config({k: v for k, v in new_config.items() if k != "password"})
            self.config = new_config
            return True
        return False

    def check_build_files(self):
        app_vdf_path = os.path.join(self.builder_path, "app_build.vdf")
        for depot_id in self.config.get("depots", [str(int(self.config.get("app_id", "0")) + 1)]):
            print(os.path.join(self.builder_path, f"depot_build_{depot_id}.vdf"))
            
        depot_vdf_exists = all(
            os.path.exists(os.path.join(self.builder_path, f"depot_build_{depot_id}.vdf"))
            for depot_id in self.config.get(
                "depots", [str(int(self.config.get("app_id", "0")) + 1)]
            )
        )
        return (
            os.path.exists(self.builder_path)
            and os.path.exists(app_vdf_path)
            and depot_vdf_exists
        )

    def publish(self, parent=None):
        if not self.config.get("app_id") or not self.config.get("username"):
            QMessageBox.warning(
                parent,
                "Config Error",
                "Steam configuration is incomplete. Please configure first.",
            )
            return

        if not self.check_build_files():
            wizard = SteamBuildSetupWizard(self.build_path, self.config, parent)
            if wizard.exec() == 1:  # Check for Finish (1)
                wizard.generate_files()
            else:
                return  # User cancelled wizard

        builder_path = os.path.normpath(os.path.join(self.build_path, "Steam/builder"))  # Match wizard default
        dialog = SteamUploadDialog(builder_path, self.config, parent=parent)
        dialog.exec()
