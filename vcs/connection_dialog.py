import multiprocessing
from vcs.p4client import P4Client
from PyQt6.QtWidgets import QFormLayout, QLineEdit, QDialogButtonBox, QDialog, QPushButton, QLabel, QMessageBox

def connect_in_process(
    vcs_type,
    port: str,
    user: str,
    password: str,
    client: str,
    result_queue: multiprocessing.Queue,
):
    """Run connection test in a separate process using the specified VCS type."""
    result, error_msg = vcs_type.test_connection(port, user, password)
    result_queue.put((result, error_msg))


class ConnectionSettingsDialog(QDialog):
    def __init__(self, current_config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Perforce Connection Settings")
        self.current_config = current_config.get("perforce", {}).get(
            "config_override", {}
        )
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
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        test_button = QPushButton("Test Connection")
        test_button.clicked.connect(self.test_connection_with_feedback)

        layout.addWidget(test_button)
        layout.addWidget(buttons)

        if self.has_existing_config:
            layout.insertRow(0, QLabel("Editing existing connection settings:"))

    def test_connection_with_feedback(self):
        result, error_msg = self.test_connection()
        if result == "success":
            QMessageBox.information(self, "Connection Test", "Connection successful!")
        else:
            QMessageBox.critical(self, "Connection Test", f"Connection failed: {error_msg}")

    def test_connection(self):
        """Test the Perforce connection with the current input values from the UI."""
        result_queue = multiprocessing.Queue()
        port = self.port_input.text()
        user = self.user_input.text()
        password = self.password_input.text()
        client = self.client_input.text()

        process = multiprocessing.Process(
            target=connect_in_process,
            args=(P4Client, port, user, password, client, result_queue),
        )
        process.start()
        process.join(timeout=5)

        if process.is_alive():
            process.terminate()
            process.join()
            return "error", "Connection timed out: Server not responding."
        else:
            if not result_queue.empty():
                return result_queue.get()
            return "error", "Connection failed: No response from process."

    def get_config(self):
        return {
            "perforce": {
                "config_override": {
                    "p4port": self.port_input.text(),
                    "p4user": self.user_input.text(),
                    "p4password": self.password_input.text(),
                    "p4client": self.client_input.text(),
                }
            }
        }

    def accept(self):
        result, error_msg = self.test_connection()
        if result == "success":
            super().accept()
        else:
            QMessageBox.critical(
                self,
                "Connection Test",
                f"Connection failed: {error_msg}\nPlease correct the settings.",
            )