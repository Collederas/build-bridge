import os
import subprocess
import json
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
)
from PyQt6.QtCore import QThread, pyqtSignal
from publisher.base_publisher import BasePublisher
from publisher.steam.steam_wizard import SteamBuildSetupWizard
from app_config import ConfigManager



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
    def __init__(self, config, steamcmd_path="C:/steamcmd/steamcmd.exe", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Upload to Steam")

        self.vdf_file = os.path.join(config["builder_path"], "app_build.vdf")

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
        self.thread.log_signal.connect(self.log_progress)
        self.thread.finished_signal.connect(self.upload_finished)
        self.thread.start()

    def log_progress(self):
        pass

    def upload_finished(self, success):
        self.cancel_btn.setText("Close")
        if success:
            self.log_display.append("Upload completed successfully!")
        else:
            self.log_display.append("Upload failed. Check logs for details.")


class SteamPublisher(BasePublisher):
    KEYRING_SERVICE = "BuildBridgeSteam"

    def __init__(self):        
        # Use ConfigManager for stores. Probably at some point would
        # be good to support multiple projects so config should be per-project.
        self.config_manager = ConfigManager("stores")
        
        # Get basic config data
        self.app_id = self.config_manager.get("steam.app_id", "")
        self.username = self.config_manager.get("steam.username", "")
        
        # Load password from keyring if username is available
        self.password = ""
        if self.username:
            self.password = self.config_manager.get_secure(self.KEYRING_SERVICE, self.username) or ""
        
        self.config = {
            "app_id": self.app_id,
            "username": self.username,
            "password": self.password,
            "depots": self.config_manager.get("steam.depots", []),
            "builder_path": self.config_manager.get("steam.builder_path", "")
        }

    def check_build_files(self):
        builder_path = self.config["builder_path"]
        app_vdf_path = os.path.join(builder_path, "app_build.vdf")
        
        # Get depot IDs or use default (app_id + 1)
        depot_ids = self.config.get("depots", [])
        if not depot_ids and self.app_id:
            depot_ids = [str(int(self.app_id) + 1)]
        
        # Check if all depot VDF files exist
        depot_vdf_exists = all(
            os.path.exists(os.path.join(builder_path, f"depot_build_{depot_id}.vdf"))
            for depot_id in depot_ids
        ) if depot_ids else False
        
        return (
            os.path.exists(self.builder_path)
            and os.path.exists(app_vdf_path)
            and depot_vdf_exists
        )

    def publish(self, parent=None):
        if not self.app_id or not self.username:
            QMessageBox.warning(
                parent,
                "Config Error",
                "Steam configuration is incomplete. Please configure first.",
            )
            return False

        dialog = SteamUploadDialog(self.config, parent=parent)
        return dialog.exec() == QDialog.DialogCode.Accepted