import sys
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QMenu,
)
from PyQt6.QtGui import QIcon


from core.vcs.p4client import P4Client
from database import SessionFactory, initialize_database
from models import BuildTarget, Project
from views.widgets.build_targets_widget import BuildTargetListWidget
from views.widgets.publish_targets_widget import PublishTargetsListWidget
from views.dialogs.settings_dialog import SettingsDialog


class BuildBridgeWindow(QMainWindow):
    vcs_clients = (P4Client,)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Build Bridge")
        self.setWindowIcon(QIcon("icons/buildbridge.ico"))
        self.setGeometry(100, 100, 700, 500)

        self.session = SessionFactory()

        # One day, support multiproject. For now, this will do.
        self.project = self.session.query(Project).first()

        # Single build target setup too.
        self.build_target = (
            self.session.query(BuildTarget).order_by(BuildTarget.id.desc()).first()
        )

        self.vcs_client = None

        self.build_list_widget = None
        self.init_ui()

    def init_ui(self):
        # Menu Bar
        menu_bar = self.menuBar()
        file_menu = QMenu("&File", self)
        menu_bar.addMenu(file_menu)
        settings_action = file_menu.addAction("Settings")
        settings_action.triggered.connect(self.open_settings_dialog)

        # Central Widget and Main Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)  # Add some spacing between sections

        # Build Targt Section
        build_target_widget = BuildTargetListWidget(
            build_target=self.build_target, parent=self
        )
        build_target_widget.build_ready_signal.connect(self.on_new_build_available)
        main_layout.addWidget(build_target_widget)

        # Builds Section
        builds_widget = QWidget()
        builds_layout = QVBoxLayout(builds_widget)
        heading_label = QLabel("Available Builds")
        heading_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        builds_layout.addWidget(heading_label)

        self.build_list_widget = PublishTargetsListWidget(
            self.project.builds_path if self.project else ""
        )

        self.build_list_widget.setMinimumHeight(100)
        builds_layout.addWidget(self.build_list_widget)

        main_layout.addWidget(builds_widget)

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        result = dialog.exec()
        if result:
            self.build_list_widget.refresh_builds(self.project.builds_path)

    def get_selected_branch(self):
        selected_items = self.branch_list.selectedItems()
        if not selected_items:
            return None
        return selected_items[0].text()

    def on_new_build_available(self, build_dir):
        print(f"New build available at {build_dir}")

        # Hm... build_dir is the archive dir: it has no Project Name joined to it
        # but still this is not good because it's the build widget that should tell us
        # where the new build is.
        self.build_list_widget.refresh_builds(self.project.builds_path)

    def focusInEvent(self, a0):
        self.build_list_widget.refresh_builds(self.project.builds_path)
        return super().focusInEvent(a0)

    def closeEvent(self, event):
        if self.vcs_client:
            self.vcs_client._disconnect()

        super().closeEvent(event)


def main():
    initialize_database()

    app = QApplication(sys.argv)
    window = BuildBridgeWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
