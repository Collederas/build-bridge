import sys
import p4sync
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QListWidget,
    QVBoxLayout,
    QPushButton,
    QComboBox,
    QProgressBar,
    QTextEdit,
    QWidget,
)


class GameManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GameManager")

        # Create the main widget
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)

        # Create layout
        layout = QVBoxLayout()

        # Button for Sync
        self.sync_button = QPushButton("Sync Repository")
        layout.addWidget(self.sync_button)

        # List to display branches (updated for PyQt6)
        self.branch_list = QListWidget()
        layout.addWidget(self.branch_list)

        # Button for Build
        self.build_button = QPushButton("Build")
        layout.addWidget(self.build_button)

        # Button for Deploy
        self.deploy_button = QPushButton("Deploy")
        layout.addWidget(self.deploy_button)

        # Progress bar for Sync/Build/Deploy
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        # Text edit area for logs
        self.log_area = QTextEdit()
        layout.addWidget(self.log_area)

        # Set the layout for the main widget
        self.main_widget.setLayout(layout)

        # Connect buttons to methods
        self.sync_button.clicked.connect(self.sync_repo)
        self.build_button.clicked.connect(self.build_game)
        self.deploy_button.clicked.connect(self.deploy_game)

    def sync_repo(self):
        # Placeholder for sync logic
        self.update_log("Syncing repository...")
        self.progress_bar.setValue(20)
        branches = p4sync.sync_perforce_repo()
        self.display_branches(branches)

    def display_branches(self, branches):
        # Clear previous list and add new branches to the list widget
        self.branch_list.clear()
        for branch in branches:
            self.branch_list.addItem(branch)

    def build_game(self):
        # Placeholder for build logic
        self.update_log("Building game...")
        self.progress_bar.setValue(60)

    def deploy_game(self):
        # Placeholder for deploy logic
        self.update_log("Deploying game...")
        self.progress_bar.setValue(100)

    def update_log(self, message):
        self.log_area.append(message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GameManagerApp()
    window.show()
    sys.exit(app.exec())
