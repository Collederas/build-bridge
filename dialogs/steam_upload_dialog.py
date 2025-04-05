from pathlib import Path, WindowsPath
from PyQt6.QtCore import QProcess
from PyQt6.QtWidgets import QVBoxLayout, QTextEdit, QLabel, QPushButton, QDialog

class SteamUploadDialog(QDialog):
    def __init__(
        self,
        builder_path: str,
        steam_username: str,
        steamcmd_path="C:/steamcmd/steamcmd.exe",
    ):
        super().__init__()
        self.vdf_file = WindowsPath(builder_path) / "app_build.vdf"
        
        self.steamcmd_path = steamcmd_path
        self.steam_username = steam_username

        self.setup_ui()
        self.setWindowTitle("Upload to Steam")
        self.setup_process()
        self.start_upload()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel(f"Uploading: {self.vdf_file}"))
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        layout.addWidget(self.log_display)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_upload)
        layout.addWidget(self.cancel_btn)
        self.setLayout(layout)

    def setup_process(self):
        self.process = QProcess(self)
        # Merge stdout and stderr into a single stream
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)        
        self.process.readyReadStandardOutput.connect(self.read_stdout)
        self.process.readyReadStandardError.connect(self.read_stderr)
        self.process.finished.connect(self.upload_finished)
        self.process.errorOccurred.connect(self.process_error)

    def read_stdout(self):
        data = self.process.readAllStandardOutput()
        if data:
            text = data.data().decode(errors="ignore")
            self.log_display.append(f"STDOUT: {text}")
            print(f"Stdout received: {text}")  # For debugging

    def read_stderr(self):
        data = self.process.readAllStandardError()
        if data:
            text = data.data().decode(errors="ignore")
            self.log_display.append(f"STDERR: {text}")
            print(f"Stderr received: {text}")  # For debugging
            
    def start_upload(self):
        cmd = [
                "cmd.exe",
                "/c",
                self.steamcmd_path,
                "-console",
                "+login",
                self.steam_username,
                "+run_app_build",
                str(self.vdf_file),
                "+quit"
            ]
        self.log_display.append(f"Running: {' '.join(cmd)}")
        self.process.setWorkingDirectory(str(self.vdf_file.parent))
        self.process.start(cmd[0], cmd[1:])
    
    def cancel_upload(self):
        if self.process.state() == QProcess.ProcessState.Running:
            self.process.kill()
        self.reject()

    def upload_finished(self, exit_code, exit_status):
        self.cancel_btn.setText("Close")
        if exit_code == 0 and exit_status == QProcess.ExitStatus.NormalExit:
            self.log_display.append("Upload completed successfully!")
        else:
            self.log_display.append("Upload failed. Check logs for details.")

    def process_error(self, error):
        error_messages = {
            QProcess.ProcessError.FailedToStart: "The process failed to start. Ensure the steamcmd path is correct.",
            QProcess.ProcessError.Crashed: "The process crashed unexpectedly.",
            QProcess.ProcessError.Timedout: "The process timed out.",
            QProcess.ProcessError.WriteError: "An error occurred while writing to the process.",
            QProcess.ProcessError.ReadError: "An error occurred while reading from the process.",
            QProcess.ProcessError.UnknownError: "An unknown error occurred.",
        }
        self.log_display.append(f"Error: {error_messages.get(error, 'An unexpected error occurred.')}")
        self.cancel_btn.setText("Close")