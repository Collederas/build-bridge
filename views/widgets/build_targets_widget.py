from pathlib import Path
import shutil
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
    QVBoxLayout,
    QFrame,
)

from core.builder.unreal_builder import (
    EngineVersionError,
    ProjectFileNotFoundError,
    UnrealBuilder,
    UnrealEngineNotInstalledError,
)
from database import session_scope
from models import BuildTarget
from views.dialogs.build_dialog import BuildWindowDialog
from views.dialogs.build_target_setup_dialog import BuildTargetSetupDialog


class BuildTargetListWidget(QWidget):
    """Lists the available Build Targets"""

    def __init__(self, build_target: BuildTarget, parent=None):
        super().__init__()
        self.parent = parent
        self.vcs_client = parent.vcs_client
        self.build_target = build_target

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        # Contrast frame
        contrast_frame = QFrame()
        contrast_frame.setObjectName("contrastFrame")
        contrast_frame.setFrameShape(QFrame.Shape.StyledPanel)

        # Scoped style just to this frame
        contrast_frame.setStyleSheet(
            """
            QFrame#contrastFrame {
                background-color: #f9f9f9;
                border: 1px solid #ccc;
                border-radius: 6px;
                padding: 10px;
            }
        """
        )

        layout = QHBoxLayout(contrast_frame)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        layout.addWidget(QLabel("Builds:"))


        self.label = QLabel("Missing Build Target")

        # Branches
        self.build_version = QLineEdit("0.1")

        self.build_button = QPushButton("Build")
        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self.open_edit_dialog)
        self.build_button.clicked.connect(self.trigger_build)

        if self.build_target:
            self.build_button.setEnabled(True)
            self.label.setText(self.build_target.__repr__())
        else:
            self.build_button.setEnabled(False)

        layout.addWidget(self.label)
        layout.addWidget(self.build_version)
        layout.addWidget(self.edit_button)
        layout.addWidget(self.build_button)

        outer_layout.addWidget(contrast_frame)

    def open_edit_dialog(self):
        # If a target exists use that. Else it will be created at the end
        # of the dialog, when accepted.
        build_target_id = self.build_target.id if self.build_target else None
        dialog = BuildTargetSetupDialog(build_target_id=build_target_id)
        dialog.exec()

    def trigger_build(self):
        """
        We use the VCS branch name (or tag/label, when that is supported) to name
        each packaged build.
        eg.:
            BuildDir
                |_ ProjectName
                    |_ StoresConfig
                        |_ Steam
                        |_ Itch
                    |_ Release1 (VCS branch/tag)
                    |_ Release2 (VCS branch/tag)
        """
        builds_root = self.build_target.archive_directory
        release_name = self.build_version.text().strip()

        project_build_dir_root = (
            Path(builds_root) / self.build_target.project.name / release_name
        )

        source_dir = self.build_target.project.source_dir

        # Check if build directory exists before trying to create the builder
        if project_build_dir_root.exists():
            response = QMessageBox.question(
                self,
                "Build Conflict",
                f"A build already exists for release:\n{release_name}\n\nDo you want to proceed and overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if response == QMessageBox.StandardButton.No:
                return

            try:
                shutil.rmtree(project_build_dir_root)
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Cleanup Error",
                    f"Failed to delete existing build directory:\n{str(e)}",
                )
                return

        # Create the builder after any potential cleanup
        try:
            unreal_builder = UnrealBuilder(
                source_dir=source_dir,
                engine_path="C:/Program Files/Epic Games",
                target_platform=self.build_target.target_platform.value,
                target_config=self.build_target.build_type.value,
                output_dir=project_build_dir_root,
                clean=False,
                valve_package_pad=self.build_target.optimize_for_steam,
            )
        except ProjectFileNotFoundError as e:
            QMessageBox.critical(
                self, "Project File Error", f"Project file not found: {str(e)}"
            )
            return
        except EngineVersionError as e:
            QMessageBox.critical(
                self,
                "Engine Version Error",
                f"Could not determine Unreal Engine version: {str(e)}",
            )
            return
        except UnrealEngineNotInstalledError as e:
            QMessageBox.critical(
                self,
                "Unreal Engine Not Found",
                f"Unreal Engine not found at the expected path",
            )
            return

        # Continue with the build process
        dialog = BuildWindowDialog(unreal_builder, parent=self)
        dialog.exec()
