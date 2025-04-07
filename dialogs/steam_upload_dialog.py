from pathlib import Path
from PyQt6.QtCore import QProcess
from PyQt6.QtWidgets import QVBoxLayout, QTextEdit, QLabel, QPushButton, QDialog

from conf.config_manager import ConfigManager

class SteamUploadDialog(QDialog):
    def __init__(self, builder_path: str, steam_username: str, steamcmd_path="C:/steamcmd/steamcmd.exe"):
        super().__init__()
        self.vdf_file = Path(builder_path) / "app_build.vdf"
        self.steamcmd_path = steamcmd_path
        self.steam_username = steam_username
        self.setup_ui()
        self.setup_process()
        self.setWindowTitle("Upload to Steam")
        self.start_full_workflow()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel(f"Uploading: {self.vdf_file}"))
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        layout.addWidget(self.log_display)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_process)
        layout.addWidget(self.cancel_btn)
        self.setLayout(layout)

    def setup_process(self):
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self.read_stdout)
        self.process.readyReadStandardError.connect(self.read_stderr)
        self.process.finished.connect(self.handle_process_finished)
        self.process.errorOccurred.connect(self.handle_process_error)

    def read_stdout(self):
        data = self.process.readAllStandardOutput().data().decode(errors="ignore")
        if data:
            self.log_display.append(f"STDOUT: {data}")

    def read_stderr(self):
        data = self.process.readAllStandardError().data().decode(errors="ignore")
        if data:
            self.log_display.append(f"STDERR: {data}")

    def start_full_workflow(self):
        self.log_display.append("Starting SteamCMD workflow...")
        conf = ConfigManager("store")
        passw = conf.get_secure("BuildBridgeSteam", self.steam_username)
        command = [
            self.steamcmd_path,
            "+login", self.steam_username, passw,
            "+run_app_build", f'"{self.vdf_file}"',  # Quote the VDF path explicitly
            "+quit"
        ]
        self.log_display.append("Please check Steam Guard on your phone if prompted.")
        self.run_command(command, self.handle_workflow_result)

    def handle_workflow_result(self, exit_code):
        output = self.log_display.toPlainText()
        if exit_code == 0 and "successfully" in output.lower():
            self.log_display.append("Upload completed successfully!")
            self.cancel_btn.setText("Close")
            self.cancel_btn.clicked.connect(self.accept)
        elif "Logged in OK" not in output:
            self.log_display.append("Login failed. Please check your credentials.")
        else:
            self.log_display.append("Upload failed. Check logs for details.")

    def run_command(self, command, callback):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.log_display.append("Error: Another process is already running.")
            return
        self.process.finished.disconnect()
        self.process.finished.connect(lambda exit_code, _: callback(exit_code))
        # Join the command with spaces and ensure the quoted VDF path is preserved
        full_command = f'& {command[0]} {" ".join(str(arg) for arg in command[1:])}'
        self.process.start("powershell.exe", ["-Command", full_command])

    def cancel_process(self):
        if self.process.state() == QProcess.ProcessState.Running:
            self.log_display.append("Terminating the current process...")
            self.process.kill()
        self.process.waitForFinished()
        self.log_display.append("Process terminated.")
        self.reject()

    def handle_process_finished(self, exit_code, exit_status):
        self.log_display.append(f"Process finished with exit code {exit_code}, status {exit_status}")

    def handle_process_error(self, error):
        error_messages = {
            QProcess.ProcessError.FailedToStart: "The process failed to start. Ensure the steamcmd path is correct.",
            QProcess.ProcessError.Crashed: "The process crashed unexpectedly.",
            QProcess.ProcessError.Timedout: "The process timed out.",
            QProcess.ProcessError.WriteError: "An error occurred while writing to the process.",
            QProcess.ProcessError.ReadError: "An error occurred while reading from the process.",
            QProcess.ProcessError.UnknownError: "An unknown error occurred.",
        }
        self.log_display.append(f"Error: {error_messages.get(error, 'An unexpected error occurred.')}")