import sys, logging
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QDialog,
    QLabel,
    QMenu,
)
from PyQt6.QtGui import QIcon

from build_bridge.log import setup_logging
from build_bridge.utils.paths import get_resource_path

from build_bridge.database import SessionFactory, create_or_update_db
from build_bridge.models import Project
from build_bridge.views.widgets.build_targets_widget import BuildTargetListWidget
from build_bridge.views.widgets.publish_profile_read_widgets import (
    PublishProfileListWidget,
)
from build_bridge.views.dialogs.settings_dialog import SettingsDialog
from build_bridge.style.app_style import MAIN_WINDOW_STYLE


class BuildBridgeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Build Bridge")
        self.setWindowIcon(QIcon(str(get_resource_path("build_bridge/icons/buildbridge.ico"))))
        self.setGeometry(100, 100, 860, 620)
        self.setMinimumSize(760, 520)

        self.session = SessionFactory()
        self.project = self.session.query(Project).first()

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
        central_widget.setObjectName("mainContent")
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(24, 20, 24, 24)
        main_layout.setSpacing(18)

        # Build Target Section
        project_id = self.project.id if self.project else None
        build_target_widget = BuildTargetListWidget(project_id=project_id, parent=self)
        build_target_widget.build_ready_signal.connect(self.refresh_builds)
        main_layout.addWidget(build_target_widget)

        # Builds Section
        builds_widget = QWidget()
        builds_layout = QVBoxLayout(builds_widget)
        builds_layout.setContentsMargins(0, 0, 0, 0)
        builds_layout.setSpacing(10)

        heading_row = QWidget()
        heading_row.setObjectName("sectionHeader")
        heading_layout = QHBoxLayout(heading_row)
        heading_layout.setContentsMargins(0, 0, 0, 0)
        heading_layout.setSpacing(8)

        heading_label = QLabel("Available Builds")
        heading_label.setObjectName("sectionTitle")
        heading_layout.addWidget(heading_label)
        heading_layout.addStretch(1)
        builds_layout.addWidget(heading_row)

        self.build_list_widget = PublishProfileListWidget()
        self.build_list_widget.setMinimumHeight(100)
        builds_layout.addWidget(self.build_list_widget)

        main_layout.addWidget(builds_widget)
        main_layout.setStretchFactor(builds_widget, 1)

        if not self.project or not self.project.is_valid():
            self.statusBar().showMessage(
                "Welcome! Go to File > Settings to configure your project before adding a build target.",
                0,
            )

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.monitored_dir_changed_signal.connect(self.refresh_builds)
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            logging.info("Settings accepted, refreshing main window project data...")
            try:
                if self.project:
                    self.session.refresh(self.project)
                    logging.info(f"Refreshed project '{self.project.name}' in main window session.")
                else:
                    self.project = self.session.query(Project).first()
                    if self.project:
                        logging.info(f"Loaded newly created project '{self.project.name}' into main window.")
                self.build_list_widget.refresh_builds()
            except Exception as e:
                logging.info(f"Error refreshing project in main window after settings: {e}")

    def refresh_builds(self):
        self.build_list_widget.refresh_builds()

    def closeEvent(self, event):
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(MAIN_WINDOW_STYLE)
    window = BuildBridgeWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    setup_logging()
    create_or_update_db()
    main()
