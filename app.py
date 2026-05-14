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
    QComboBox,
    QPushButton,
    QSizePolicy,
)
from PyQt6.QtGui import QIcon

from build_bridge.log import setup_logging
from build_bridge.utils.paths import get_resource_path

from build_bridge.database import SessionFactory, create_or_update_db
from build_bridge.models import Project
from build_bridge.core.projects import get_active_project, set_active_project
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
        self.project = self.load_active_project()

        self.build_list_widget = None
        self.build_target_widget = None
        self.project_combo = None
        self.init_ui()

    def init_ui(self):
        # Menu Bar
        menu_bar = self.menuBar()
        file_menu = QMenu("&File", self)
        menu_bar.addMenu(file_menu)
        settings_action = file_menu.addAction("Settings")
        settings_action.triggered.connect(self.open_settings_dialog)
        new_project_action = file_menu.addAction("New Project")
        new_project_action.triggered.connect(self.open_new_project_dialog)

        # Central Widget and Main Layout
        central_widget = QWidget()
        central_widget.setObjectName("mainContent")
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(24, 20, 24, 24)
        main_layout.setSpacing(18)

        project_row = QWidget()
        project_row.setObjectName("sectionHeader")
        project_layout = QHBoxLayout(project_row)
        project_layout.setContentsMargins(0, 0, 0, 0)
        project_layout.setSpacing(8)

        project_label = QLabel("Project")
        project_label.setObjectName("sectionTitle")
        project_layout.addWidget(project_label)

        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(240)
        self.project_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.project_combo.currentIndexChanged.connect(self.on_project_changed)
        project_layout.addWidget(self.project_combo)

        edit_project_button = QPushButton("Edit")
        edit_project_button.setObjectName("ghostButton")
        edit_project_button.clicked.connect(self.open_settings_dialog)
        project_layout.addWidget(edit_project_button)

        new_project_button = QPushButton("+ New")
        new_project_button.setObjectName("ghostButton")
        new_project_button.clicked.connect(self.open_new_project_dialog)
        project_layout.addWidget(new_project_button)
        project_layout.addStretch(1)
        main_layout.addWidget(project_row)
        self.refresh_project_selector()

        # Build Target Section
        project_id = self.project.id if self.project else None
        self.build_target_widget = BuildTargetListWidget(project_id=project_id, parent=self)
        self.build_target_widget.build_ready_signal.connect(self.refresh_builds)
        main_layout.addWidget(self.build_target_widget)

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

        self.build_list_widget = PublishProfileListWidget(project_id=project_id)
        self.build_list_widget.setMinimumHeight(100)
        builds_layout.addWidget(self.build_list_widget)

        main_layout.addWidget(builds_widget)
        main_layout.setStretchFactor(builds_widget, 1)

        if not self.project or not self.project.is_valid():
            self.statusBar().showMessage(
                "Welcome! Go to File > Settings to configure your project before adding a build target.",
                0,
            )

    def refresh_project_selector(self):
        if self.project_combo is None:
            return

        self.project_combo.blockSignals(True)
        self.project_combo.clear()

        with SessionFactory() as session:
            projects = session.query(Project).order_by(Project.name.asc(), Project.id.asc()).all()

        if not projects:
            self.project_combo.addItem("No projects configured", None)
            self.project_combo.setEnabled(False)
            self.project_combo.blockSignals(False)
            return

        self.project_combo.setEnabled(True)
        for project in projects:
            label = project.name or f"Project {project.id}"
            self.project_combo.addItem(label, project.id)

        if self.project:
            index = self.project_combo.findData(self.project.id)
            if index >= 0:
                self.project_combo.setCurrentIndex(index)

        self.project_combo.blockSignals(False)

    def load_active_project(self):
        with SessionFactory() as session:
            project = get_active_project(session)
            project_id = project.id if project else None
            session.commit()

        self.session.expire_all()
        return self.session.get(Project, project_id) if project_id else None

    def on_project_changed(self, index):
        if index < 0:
            return

        project_id = self.project_combo.itemData(index)
        if project_id == (self.project.id if self.project else None):
            return

        try:
            self.project = set_active_project(self.session, project_id)
            self.session.commit()
            self.refresh_project_views()
        except Exception as e:
            self.session.rollback()
            logging.info(f"Error changing active project: {e}", exc_info=True)

    def refresh_project_views(self):
        project_id = self.project.id if self.project else None
        if self.build_target_widget is not None:
            self.build_target_widget.set_project_id(project_id)
        if self.build_list_widget is not None:
            self.build_list_widget.set_project_id(project_id)

    def open_settings_dialog(self):
        project_id = self.project.id if self.project else None
        dialog = SettingsDialog(self, project_id=project_id)
        dialog.monitored_dir_changed_signal.connect(self.refresh_builds)
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            logging.info("Settings accepted, refreshing main window project data...")
            try:
                self.project = self.load_active_project()
                self.refresh_project_selector()
                self.refresh_project_views()
            except Exception as e:
                logging.info(f"Error refreshing project in main window after settings: {e}")

    def open_new_project_dialog(self):
        dialog = SettingsDialog(self, new_project=True)
        dialog.monitored_dir_changed_signal.connect(self.refresh_builds)
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            try:
                self.project = self.load_active_project()
                self.refresh_project_selector()
                self.refresh_project_views()
            except Exception as e:
                logging.info(f"Error refreshing project after creation: {e}")

    def refresh_builds(self):
        self.build_list_widget.refresh_builds()

    def closeEvent(self, event):
        self.session.close()
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
