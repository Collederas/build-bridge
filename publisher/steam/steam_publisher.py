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

    def log_progress(self, message):
        # Fixed the missing parameter
        self.log_display.append(message)

    def upload_finished(self, success):
        self.cancel_btn.setText("Close")
        if success:
            self.log_display.append("Upload completed successfully!")
        else:
            self.log_display.append("Upload failed. Check logs for details.")


class SteamPublisher(BasePublisher):
    KEYRING_SERVICE = "BuildBridgeSteam"

    def __init__(self):        
        # Use ConfigManager for stores
        self.config_manager = ConfigManager("stores")
        
        # Get basic config data
        self.app_id = self.config_manager.get("steam.app_id", "")
        self.username = self.config_manager.get("steam.username", "")
        
        # Load password from keyring if username is available
        self.password = ""
        if self.username:
            self.password = self.config_manager.get_secure(self.KEYRING_SERVICE, self.username) or ""
        
        # Load other config values
        self.builder_path = self.config_manager.get("steam.builder_path", "")
        self.depots = self.config_manager.get("steam.depots", [])
        
        self.config = {
            "app_id": self.app_id,
            "username": self.username,
            "password": self.password,
            "depots": self.depots,
            "builder_path": self.builder_path
        }

    def check_build_files(self) -> bool:
        """Check if necessary build files exist"""
        if not self.builder_path:
            return False
            
        app_vdf_path = os.path.join(self.builder_path, "app_build.vdf")
        
        # Get depot IDs or use default (app_id + 1)
        depot_ids = self.depots
        if not depot_ids and self.app_id:
            depot_ids = [str(int(self.app_id) + 1)]
        
        # Check if all depot VDF files exist
        depot_vdf_exists = all(
            os.path.exists(os.path.join(self.builder_path, f"depot_build_{depot_id}.vdf"))
            for depot_id in depot_ids
        ) if depot_ids else False
        
        return (
            os.path.exists(self.builder_path)
            and os.path.exists(app_vdf_path)
            and depot_vdf_exists
        )

    def configure(self, build_path, parent=None):
        """Open the configuration wizard to set up Steam publishing"""
        wizard = SteamBuildSetupWizard(build_path, self.config, parent=parent)
        
        if wizard.exec() == QDialog.DialogCode.Accepted:
            # Reload configuration after wizard completes
            self.__init__()  # Re-initialize to load updated config
            return True
            
        return False

    def publish(self, parent=None):
        """Start the Steam publishing process"""
        # Check if we have necessary configuration
        if not self.app_id or not self.username:
            msg = QMessageBox.question(
                parent,
                "Steam Configuration",
                "Steam configuration is incomplete. Would you like to configure it now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if msg == QMessageBox.StandardButton.Yes:
                # Get the build path from caller
                build_path = parent.get_build_path() if hasattr(parent, "get_build_path") else ""
                if not build_path:
                    build_path = os.getcwd()
                
                # Open configuration wizard
                if self.configure(build_path, parent):
                    # If configuration was successful, check build files
                    if not self.check_build_files():
                        QMessageBox.warning(
                            parent, 
                            "Build Files Missing",
                            "Some required build files are missing. Please ensure all files are properly configured."
                        )
                        return False
                else:
                    return False
            else:
                return False

        if not self.check_build_files():
            dialog = SteamBuildSetupWizard(self)
        # Create and execute upload dialog
        dialog = SteamUploadDialog(self.config, parent=parent)
        return dialog.exec() == QDialog.DialogCode.Accepted

    def save_credentials(self, username, password):
        """Save username and password to the config and keyring"""
        # Save username to config
        self.config_manager.set("steam.username", username)
        
        # Save password to keyring
        self.config_manager.set_secure(self.KEYRING_SERVICE, username, password)
        
        # Save config to disk
        self.config_manager.save()
        
        # Update local variables
        self.username = username
        self.password = password
        self.config["username"] = username
        self.config["password"] = password