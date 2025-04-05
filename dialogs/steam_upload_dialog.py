from pathlib import Path
from PyQt6.QtCore import QProcess, QTimer
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QTextEdit,
    QLabel,
    QPushButton,
    QDialog,
    QLineEdit,
    QFormLayout,
    QDialogButtonBox,
)

from conf.config_manager import ConfigManager


class LoginDialog(QDialog):
    def __init__(self, username, steamcmd_path, parent=None):
        super().__init__(parent)
        self.username = username
        self.steamcmd_path = steamcmd_path
        self.password = ""
        self.process = None
        self.setup_ui()
        self.setup_process()

    def setup_ui(self):
        self.setWindowTitle("Steam Login")
        layout = QVBoxLayout()

        explanation = QLabel(
            "SteamCMD requires login credentials to upload your app.\n"
            "Enter your Steam password and, if prompted, your Steam Guard code."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        layout.addWidget(QLabel("Status:"))
        layout.addWidget(self.log_display)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.try_login)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.setLayout(layout)

    def setup_process(self):
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.process_finished)

    def read_output(self):
        if self.process is None:  # Guard against process being None
            return
        data = self.process.readAllStandardOutput()
        if data:
            text = data.data().decode(errors="ignore")
            self.log_display.append(text)

    def try_login(self):
        # Retrieve password from ConfigManager if available
        config_manager = ConfigManager("stores")
        username = config_manager.get("steam.username", "")
        password = config_manager.get_secure("BuildBridgeSteam", username)

        if not password:
            raise Exception(
                f"No password found in User Config for service BuildBridgeSteam, user: {username}."
            )

        self.log_display.append("Attempting login...")
        cmd = [
            "cmd.exe",
            "/c",
            self.steamcmd_path,
            "+login",
            self.username,
            password,
            "+quit",
        ]

        self.process.start(cmd[0], cmd[1:])

    def process_finished(self, exit_code, exit_status):
        if self.process is None:  # Guard against process being None
            return
        self.log_display.append(
            f"Process finished with exit code {exit_code}, status {exit_status}"
        )

        # ACCEPT = success.
        if exit_code == 0 and exit_status == QProcess.ExitStatus.NormalExit:
            self.log_display.append("Login successful! Credentials cached.")
            self.accept()
        else:
            self.log_display.append(
                f"Login failed (exit code {exit_code}). Check password or Steam Guard code."
            )

    def reject(self):
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self.process.kill()
            self.process.waitForFinished(1000)  # Wait briefly to ensure cleanup
        super().reject()

    def closeEvent(self, event):
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self.process.kill()
            self.process.waitForFinished(1000)
        event.accept()


class SteamUploadDialog(QDialog):
    """
    1.  It will launch a process to check if user is logged in using steamcmd +info.
    2.  When that process finishes it checks output to determine success. 
    3.  On success -> launch upload process (shares self.log_display with info call above)
    4.  On fail -> Launches a login dialog that tries to login using steamcmd +login.
                        on success ->   (determined checking if LoginDialog calls accept() on process finish...- bit weird)
                                        start upload
                                            -> on upload finished: log success. die.
                        on fail ->       exits with no action
    """

    def __init__(
        self,
        builder_path: str,
        steam_username: str,
        steamcmd_path="C:/steamcmd/steamcmd.exe",
    ):
        super().__init__()
        self.vdf_file = Path(builder_path) / "app_build.vdf"
        self.steamcmd_path = steamcmd_path
        self.steam_username = steam_username
        self.logged_in = False

        self.setup_ui()
        self.setWindowTitle("Upload to Steam")
        self.setup_process()
        self.login_dialog = None  # Initialize a reusable LoginDialog instance
        self.login_check()

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
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self.read_stdout)
        self.process.readyReadStandardError.connect(self.read_stderr)
        self.process.finished.connect(self.on_login_check_finished)
        self.process.errorOccurred.connect(self.process_error)

    def read_stdout(self):
        data = self.process.readAllStandardOutput()
        if data:
            self.latest_output = data.data().decode(errors="ignore")
            self.log_display.append(f"STDOUT: {self.latest_output}")

    def read_stderr(self):
        data = self.process.readAllStandardError()
        if data:
            text = data.data().decode(errors="ignore")
            self.log_display.append(f"STDERR: {text}")

    def login_check(self):
        self.log_display.append("Checking login status...")
        cmd = ["cmd.exe", "/c", self.steamcmd_path, "+info", "+quit"]
        self.process.start(cmd[0], cmd[1:])
        if not self.process.waitForStarted(5000):
            self.log_display.append("Error: Failed to start login check.")
        QTimer.singleShot(
            5000,
            lambda: (
                self.process.kill()
                if self.process.state() == QProcess.ProcessState.Running
                else None
            ),
        )

    def on_login_check_finished(self, exit_code, exit_status):
        self.log_display.append(
            f"Steam Info call process exited"
            " with exit code {exit_code}, status {exit_status}"
        )
        output = self.log_display.toPlainText()

        # Check for "Logon state" in the output
        if exit_code == 0 and "Logon state" in output and "Logged in" in output:
            self.logged_in = True
            self.start_upload()
        else:
            # Create the dialog if it doesn't exist. There another process launces to
            # run steamcmd +login and it is accepted only on success (mmmeeeh)
            if not self.login_dialog:
                self.log_display.append("Login required. Opening login dialog...")
                self.login_dialog = LoginDialog(
                    self.steam_username, self.steamcmd_path, self
                )

            # ACCEPT on the dialog = success = auth worked in login dialog's process
            if self.login_dialog.exec() == QDialog.DialogCode.Accepted:
                self.log_display.append(
                    "User logged in successfully. Starting upload..."
                )
                self.start_upload()
            else:
                self.log_display.append("Login canceled. Upload aborted.")
                return

    def start_upload(self):
        if not self.logged_in:
            self.log_display.append("Cannot upload: Not logged in.")
            return
        cmd = [
            "cmd.exe",
            "/c",
            self.steamcmd_path,
            "+login",
            self.steam_username,
            "+run_app_build",
            str(self.vdf_file),
            "+quit",
        ]
        self.log_display.append(f"Running: {' '.join(cmd)}")
        self.process.setWorkingDirectory(str(self.vdf_file.parent))
        self.process.start(cmd[0], cmd[1:])
        if not self.process.waitForStarted(5000):
            self.log_display.append("Error: Failed to start the process.")
        QTimer.singleShot(10000, self.cancel_upload)

    def cancel_upload(self):
        if self.process.state() == QProcess.ProcessState.Running:
            self.process.kill()
        self.reject()

    def on_upload_finished(self, exit_code, exit_status):
        self.cancel_btn.setText("Close")
        self.log_display.append(
            f"Upload finished with exit code {exit_code}, status {exit_status}"
        )
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
        self.log_display.append(
            f"Error: {error_messages.get(error, 'An unexpected error occurred.')}"
        )
        self.cancel_btn.setText("Close")
