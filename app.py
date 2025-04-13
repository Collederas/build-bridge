import sys
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QDialog,
    QLabel,
    QMenu,
)
from PyQt6.QtGui import QIcon

from build_bridge.utils.paths import get_resource_path

from build_bridge.database import SessionFactory, initialize_database
from build_bridge.models import BuildTarget, Project
from build_bridge.views.widgets.build_targets_widget import BuildTargetListWidget
from build_bridge.views.widgets.publish_profile_list_widget import (
    PublishProfileListWidget,
)
from build_bridge.views.dialogs.settings_dialog import SettingsDialog


class BuildBridgeWindow(QMainWindow):
    # vcs_clients = (P4Client,)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Build Bridge")
        self.setWindowIcon(QIcon(str(get_resource_path("icons/buildbridge.ico"))))
        self.setGeometry(100, 100, 700, 500)

        self.session = SessionFactory()

        # One day, support multiproject. For now, only one
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
        build_target_id = self.build_target.id if self.build_target else None
        build_target_widget = BuildTargetListWidget(
            build_target_id=build_target_id, parent=self
        )
        build_target_widget.build_ready_signal.connect(self.refresh_builds)
        main_layout.addWidget(build_target_widget)

        # Builds Section
        builds_widget = QWidget()
        builds_layout = QVBoxLayout(builds_widget)
        heading_label = QLabel("Available Builds")
        heading_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        builds_layout.addWidget(heading_label)

        self.build_list_widget = PublishProfileListWidget()

        if self.project:
            builds_dir = self.project.builds_path
        else:
            builds_dir = None

        self.build_list_widget.refresh_builds(builds_dir)

        self.build_list_widget.setMinimumHeight(100)
        builds_layout.addWidget(self.build_list_widget)

        main_layout.addWidget(builds_widget)

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        # Connect signal BEFORE exec()
        dialog.monitored_dir_changed_signal.connect(self.refresh_builds)
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            print("Settings accepted, refreshing main window project data...")
            try:
                # Re-query or refresh the project in the main window's session
                if self.project:
                    self.session.refresh(self.project)
                    print(
                        f"Refreshed project '{self.project.name}' in main window session."
                    )
                    self.build_list_widget.refresh_builds(self.project.builds_path)

                else:
                    # If no project existed initially, try loading one now
                    self.project = self.session.query(Project).first()
                    if self.project:
                        print(
                            f"Loaded newly created project '{self.project.name}' into main window."
                        )
                        self.build_list_widget.refresh_builds(self.project.builds_path)

            except Exception as e:
                print(f"Error refreshing project in main window after settings: {e}")

    def get_selected_branch(self):
        selected_items = self.branch_list.selectedItems()
        if not selected_items:
            return None
        return selected_items[0].text()

    def focusInEvent(self, a0):
        return super().focusInEvent(a0)

    def refresh_builds(self, build_dir):
        self.build_list_widget.refresh_builds(build_dir)

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
