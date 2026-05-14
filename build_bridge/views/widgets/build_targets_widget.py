import os, logging
from pathlib import Path
import shutil

from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QFrame,
    QSizePolicy,
    QMessageBox,
    QDialog,
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont

from build_bridge.core.builder.unreal_builder import (
    EngineVersionError,
    ProjectFileNotFoundError,
    UnrealBuilder,
    UnrealEngineNotInstalledError,
)
from build_bridge.core.preflight import validate_build_preflight
from build_bridge.database import session_scope
from build_bridge.models import Build, BuildStatusEnum, BuildTarget
from build_bridge.views.dialogs.build_dialog import BuildWindowDialog
from build_bridge.views.dialogs.preflight_dialog import PreflightDialog
from build_bridge.views.dialogs.build_target_setup_dialog import BuildTargetSetupDialog


class BuildTargetRow(QWidget):
    """A single row representing one BuildTarget with its build controls."""

    build_ready_signal = pyqtSignal()

    def __init__(self, build_target_id: int, parent=None):
        super().__init__(parent)
        self._build_target_id = build_target_id
        self._parent_widget = parent

        self.setObjectName("buildCard")
        row_layout = QHBoxLayout(self)
        row_layout.setContentsMargins(14, 10, 14, 10)
        row_layout.setSpacing(10)

        name_font = QFont()
        name_font.setBold(True)
        self.target_label = QLabel()
        self.target_label.setObjectName("primaryText")
        self.target_label.setFont(name_font)
        self.target_label.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)
        row_layout.addWidget(self.target_label)

        row_layout.addStretch(1)

        version_label = QLabel("Version")
        version_label.setObjectName("fieldLabel")
        row_layout.addWidget(version_label)

        self.build_version_input = QLineEdit("0.1")
        self.build_version_input.setFixedWidth(92)
        self.build_version_input.setToolTip("Version string for this build (e.g. 1.0, 0.2-beta)")
        row_layout.addWidget(self.build_version_input)

        self.edit_button = QPushButton("Edit")
        row_layout.addWidget(self.edit_button)

        self.build_button = QPushButton("Build")
        self.build_button.setObjectName("primaryButton")
        row_layout.addWidget(self.build_button)

        self.edit_button.clicked.connect(self.open_edit_dialog)
        self.build_button.clicked.connect(self.trigger_build)

        self._refresh_label()

    def _refresh_label(self):
        try:
            with session_scope() as session:
                bt = session.get(BuildTarget, self._build_target_id)
                if bt:
                    self.target_label.setText(repr(bt))
                    self.target_label.setToolTip(repr(bt))
        except Exception as e:
            logging.info(f"Error refreshing build target label: {e}")

    def open_edit_dialog(self):
        dialog = BuildTargetSetupDialog(build_target_id=self._build_target_id)
        dialog.build_target_created.connect(self._on_target_updated)
        dialog.exec()

    def _on_target_updated(self, _build_target_id: int):
        self._refresh_label()

    def trigger_build(self):
        release_name = self.build_version_input.text().strip()
        if not release_name:
            QMessageBox.warning(self, "Input Error", "Please enter a build version/release name.")
            return

        try:
            with session_scope() as session:
                current_build_target = session.get(BuildTarget, self._build_target_id)
                if not current_build_target:
                    QMessageBox.critical(self, "Error", f"Build target ID {self._build_target_id} not found.")
                    return

                # Access project to trigger lazy load
                try:
                    _ = current_build_target.project.name
                except AttributeError:
                    QMessageBox.critical(self, "Error", "Associated project data not found.")
                    return

                builds_root = current_build_target.project.archive_directory
                source_dir = current_build_target.project.source_dir
                project_name = current_build_target.project.name

                if not all([builds_root, source_dir, project_name]):
                    QMessageBox.critical(self, "Configuration Error",
                                         "Project archive directory, source directory, or name is missing.")
                    return

                preflight_result = validate_build_preflight(current_build_target, release_name)
                preflight_dialog = PreflightDialog(preflight_result, parent=self)
                if preflight_dialog.exec() != QDialog.DialogCode.Accepted:
                    return

                engine_base_path = current_build_target.unreal_engine_base_path
                if not engine_base_path or not os.path.isdir(engine_base_path):
                    QMessageBox.warning(self, "Configuration Error",
                                        "Unreal Engine base path is not configured or invalid.\n\nPlease use 'Edit' to configure it.")
                    return

                target = current_build_target.target
                if not target:
                    QMessageBox.warning(self, "Configuration Error",
                                        "No target .cs file specified.\n\nPlease use 'Edit' to configure it.")
                    return

                project_build_dir_root = current_build_target.builds_path / release_name

                if project_build_dir_root.exists():
                    response = QMessageBox.question(
                        self, "Build Conflict",
                        f"A build already exists for release:\n{release_name}\n\n"
                        f"Directory:\n{project_build_dir_root}\n\nOverwrite it?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if response == QMessageBox.StandardButton.No:
                        return
                    try:
                        shutil.rmtree(project_build_dir_root)
                        logging.info(f"Removed existing build directory: {project_build_dir_root}")
                    except Exception as e:
                        QMessageBox.critical(self, "Cleanup Error",
                                              f"Failed to delete existing build directory:\n{str(e)}")
                        return

                maps = []
                for incl_map in current_build_target.maps.keys():
                    maps.append(self._convert_umap_path(incl_map, source_dir))

                try:
                    target_platform_val = current_build_target.target_platform.value
                    build_type_val = current_build_target.build_type.value
                    optimize_steam = current_build_target.optimize_for_steam
                except AttributeError as e:
                    QMessageBox.critical(self, "Configuration Error",
                                          f"Build target missing required information: {e}")
                    return

                try:
                    unreal_builder = UnrealBuilder(
                        source_dir=source_dir,
                        engine_path=engine_base_path,
                        target_platform=target_platform_val,
                        target_config=build_type_val,
                        target=target,
                        maps=maps,
                        output_dir=project_build_dir_root,
                        clean=False,
                        valve_package_pad=optimize_steam,
                    )
                except ProjectFileNotFoundError as e:
                    QMessageBox.critical(self, "Project File Error", f"Project file not found: {str(e)}")
                    return
                except EngineVersionError as e:
                    QMessageBox.critical(self, "Engine Version Error", str(e))
                    return
                except UnrealEngineNotInstalledError as e:
                    QMessageBox.critical(self, "Unreal Engine Not Found", str(e))
                    return
                except Exception as e:
                    QMessageBox.critical(self, "Build Setup Error", f"Failed to initialize builder:\n{str(e)}")
                    return

                # Create Build record
                build_record = Build(
                    build_target_id=self._build_target_id,
                    version=release_name,
                    output_path=str(project_build_dir_root),
                    status=BuildStatusEnum.in_progress,
                )
                session.add(build_record)
                session.flush()
                build_db_id = build_record.id

            logging.info(f"Starting build dialog for release '{release_name}'...")
            dialog = BuildWindowDialog(unreal_builder, parent=self)
            dialog.build_ready_signal.connect(lambda: self._on_build_success(build_db_id))
            dialog.build_failed_signal.connect(lambda: self._on_build_failed(build_db_id))
            dialog.build_ready_signal.connect(self.build_ready_signal)
            dialog.exec()

        except Exception as e:
            logging.info(f"Error during trigger_build: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")

    def _on_build_success(self, build_id: int):
        try:
            with session_scope() as session:
                build = session.get(Build, build_id)
                if build:
                    build.status = BuildStatusEnum.success
        except Exception as e:
            logging.info(f"Failed to update build status to success: {e}")

    def _on_build_failed(self, build_id: int):
        try:
            with session_scope() as session:
                build = session.get(Build, build_id)
                if build:
                    build.status = BuildStatusEnum.failed
        except Exception as e:
            logging.info(f"Failed to update build status to failed: {e}")

    def _convert_umap_path(self, full_path: str, project_source_dir: str) -> str:
        full_path = os.path.normpath(full_path)
        project_source_dir = os.path.normpath(project_source_dir)

        if not full_path.startswith(project_source_dir):
            raise ValueError("Path is not within the project source directory")

        relative_path = os.path.relpath(full_path, project_source_dir).replace("\\", "/")
        parts = relative_path.split("/")

        if parts[0] == "Plugins":
            try:
                plugin_name = parts[2]
                content_index = parts.index("Content")
                map_subpath = parts[content_index + 1:-1]
                map_name = os.path.splitext(parts[-1])[0]
                return f"/{plugin_name}/{'/'.join(map_subpath)}/{map_name}"
            except (IndexError, ValueError):
                raise ValueError("Invalid plugin map path structure")
        else:
            try:
                if parts[0] != "Content":
                    raise ValueError("Expected path to start with 'Content'")
                map_subpath = parts[1:-1]
                map_name = os.path.splitext(parts[-1])[0]
                return f"/Game/{'/'.join(map_subpath)}/{map_name}"
            except IndexError:
                raise ValueError("Invalid base content path structure")


class BuildTargetListWidget(QWidget):
    """Lists all BuildTargets for the project, or shows an Add button."""

    build_ready_signal = pyqtSignal()

    def __init__(self, project_id: int | None, parent=None):
        super().__init__()
        self._project_id = project_id
        self._parent = parent

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(10)

        heading_label = QLabel("Build Configuration")
        heading_label.setObjectName("sectionTitle")
        outer_layout.addWidget(heading_label)

        self.targets_container = QFrame()
        self.targets_container.setObjectName("mainPanel")
        self.targets_container.setFrameShape(QFrame.Shape.StyledPanel)
        self.targets_layout = QVBoxLayout(self.targets_container)
        self.targets_layout.setContentsMargins(0, 0, 0, 0)
        self.targets_layout.setSpacing(0)

        outer_layout.addWidget(self.targets_container)

        self.add_button_row = QWidget()
        add_row_layout = QHBoxLayout(self.add_button_row)
        add_row_layout.setContentsMargins(14, 10, 14, 10)
        self.add_button = QPushButton("+ Add Build Target")
        self.add_button.setObjectName("primaryButton")
        self.add_button.clicked.connect(self._open_add_dialog)
        add_row_layout.addStretch(1)
        add_row_layout.addWidget(self.add_button)
        add_row_layout.addStretch(1)
        outer_layout.addWidget(self.add_button_row)

        self._refresh_targets()

    def _refresh_targets(self):
        # Clear existing rows
        while self.targets_layout.count():
            child = self.targets_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if self._project_id is None:
            self.targets_container.setVisible(False)
            return

        try:
            with session_scope() as session:
                targets = (
                    session.query(BuildTarget)
                    .filter_by(project_id=self._project_id)
                    .order_by(BuildTarget.id.asc())
                    .all()
                )
                target_ids = [t.id for t in targets]

            if target_ids:
                self.targets_container.setVisible(True)
                for i, bt_id in enumerate(target_ids):
                    row = BuildTargetRow(build_target_id=bt_id, parent=self)
                    row.build_ready_signal.connect(self.build_ready_signal)
                    if i > 0:
                        separator = QFrame()
                        separator.setFrameShape(QFrame.Shape.HLine)
                        separator.setFrameShadow(QFrame.Shadow.Sunken)
                        self.targets_layout.addWidget(separator)
                    self.targets_layout.addWidget(row)
            else:
                self.targets_container.setVisible(False)

        except Exception as e:
            logging.info(f"Error loading build targets: {e}", exc_info=True)
            self.targets_container.setVisible(False)

    def _open_add_dialog(self):
        dialog = BuildTargetSetupDialog(build_target_id=None)
        dialog.build_target_created.connect(self._on_target_added)
        dialog.exec()

    def _on_target_added(self, _build_target_id: int):
        self._refresh_targets()
