from pathlib import Path
import subprocess
from PyQt6.QtCore import pyqtSignal, QThread
from PyQt6.QtWidgets import QVBoxLayout, QTextEdit, QLabel, QPushButton, QDialog

from conf.config_manager import ConfigManager


class UploadThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self, steamcmd_path, builder_path, steam_username):
        super().__init__()
        self.steamcmd_path = steamcmd_path
        self.builder_path = builder_path
        self.username = steam_username

    def run(self):
        # TODO: try to run login to store token first. then run without password
        try:
            cmd = [
                self.steamcmd_path,
                "+login",
                self.username,
                "+run_app_build",
                self.builder_path,  # Assumes a VDF file exists
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
    def __init__(
        self,
        builder_path: str,
        steam_username: str,
        steamcmd_path="C:/steamworks_sdk_162/sdk/tools/ContentBuilder/builder/steamcmd.exe",
    ):
        super().__init__()  # Added call to super

        self.setWindowTitle("Upload to Steam")

        self.vdf_file = Path(builder_path) / "app_build.vdf"
        self.steamcmd_path = steamcmd_path
        self.steam_username = steam_username
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
        self.thread = UploadThread(self.steamcmd_path, self.vdf_file, self.steam_username)
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
