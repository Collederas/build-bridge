from pathlib import Path
import re
import sys
import os
import shutil
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QLabel,
    QMessageBox,
    QDialog,
    QMenu,
)
from PyQt6.QtGui import QIcon

from conf.config_manager import ConfigManager
from dialogs.build_dialog import BuildWindowDialog
from widgets.buildlist_widget import BuildListWidget
from builder.unreal_builder import (
    BuildAlreadyExistsError,
    EngineVersionError,
    ProjectFileNotFoundError,
    UnrealBuilder,
    UnrealEngineNotInstalledError,
)
from dialogs.settings_dialog import SettingsDialog
from utils.paths import unc_join_path
from vcs.p4client import P4Client
from vcs.vcsbase import MissingConfigException


class BuildBridgeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Build Bridge")
        self.setWindowIcon(QIcon("icons/buildbridge.ico"))
        self.setGeometry(100, 100, 500, 400)  # Slightly wider window

        self.project_conf = ConfigManager("project")
        self.vcs_conf = ConfigManager("vcs")
        self.build_conf = ConfigManager("build")

        self.project_name = self.project_conf.get("name")

        try:
            self.vcs_client = P4Client()
        except MissingConfigException:
            QMessageBox.warning(
                self,
                "Missing VCS Configuration",
                "VCS is not configured. Set it up in File->Settings->VCS",
            )
            self.vcs_client = None
        except ConnectionError:
            QMessageBox.warning(
                self,
                "Wrong VCS Configuration",
                "VCS is misconfigured. Check details in File->Settings->VCS",
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

        # Branches Section
        branches_widget = QWidget()
        branches_layout = QVBoxLayout(branches_widget)
        branches_layout.addWidget(QLabel("Release Branches:"))

        self.branch_list = QListWidget()
        self.branch_list.setMinimumHeight(100)
        branches_layout.addWidget(self.branch_list)

        vcs_button_layout = QHBoxLayout()

        refresh_btn = QPushButton("Refresh Branches")
        refresh_btn.clicked.connect(self.refresh_branches)
        refresh_btn.setMaximumWidth(150)
        vcs_button_layout.addWidget(refresh_btn)

        # Build Button
        build_btn = QPushButton("Build Selected Branch")
        build_btn.clicked.connect(self.trigger_build)
        build_btn.setMaximumWidth(200)
        vcs_button_layout.addWidget(build_btn)
        branches_layout.addLayout(vcs_button_layout)

        main_layout.addWidget(branches_widget)

        # Builds Section
        builds_widget = QWidget()
        builds_layout = QVBoxLayout(builds_widget)
        builds_layout.addWidget(QLabel("Available Builds:"))

        # Initialize build_list_widget without a directory initially
        self.build_list_widget = BuildListWidget(None, self)
        self.build_list_widget.setMinimumHeight(100)
        builds_layout.addWidget(self.build_list_widget)

        main_layout.addWidget(builds_widget)

        if self.vcs_client:
            self.refresh_branches()

        # Connect branch selection to update builds
        self.branch_list.itemSelectionChanged.connect(self.on_branch_selected)

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.vcs_client = P4Client()
            self.refresh_branches()
            self.project_name = self.project_conf.get("name")

    def refresh_branches(self):
        try:
            self.branch_list.clear()
            branches = self.vcs_client.get_branches()
            if not branches:
                self.branch_list.addItem("No release branches found.")
            else:
                self.branch_list.addItems(branches)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load branches: {str(e)}")


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
                        |_ Development
                        |_ Shipping
                    |_ Release2 (VCS branch/tag)
                        |_ Shipping
        """
        selected_branch = self.get_selected_branch()
        if not selected_branch:
            QMessageBox.warning(
                self, "Selection Error", "Please select a branch to build."
            )
            return

        try:
            self.vcs_client.switch_to_ref(selected_branch)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Branch Switch Failed",
                f"Could not switch to branch '{selected_branch}':\n\n{str(e)}\n\n"
                "Check your Perforce connection settings or ensure no pending changes exist.",
            )
            return

        # Extract the build parameters and validate requirements
        builds_root = self.build_conf.get("unreal.archive_directory", "C:/Builds")
        
        release_match = re.search(
            self.vcs_conf.get("perforce.release_pattern"), selected_branch
        )

        release_name = release_match.group(1) if release_match else None

        if not self.project_name:
            QMessageBox.warning(
                self,
                "No Project Name.",
                "Triggering builds depends on Project Name. Define one in File -> Settings -> Project",
            )
            return
        if not release_name:
            QMessageBox.warning(
                self,
                "Cannot get release name.",
                "We need to store the release under a folder with the name of the release."
                "We do so by inferring the release name from your release branch/stream using"
                "the regex defined in Settings -> VCS -> Release Pattern."
                "Ensure this is a valid regex that can extrapolate the release name from your" \
                " branch naming convention.",
            )
            return

        project_build_dir_root = Path(unc_join_path(builds_root, self.project_name))
        this_release_output_dir = project_build_dir_root / release_name / self.build_conf.get("unreal.build_type")
        source_dir = self.vcs_client.get_workspace_root()
        
        # Check if build directory exists before trying to create the builder
        if this_release_output_dir.exists():
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
                shutil.rmtree(this_release_output_dir)
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
                output_dir=this_release_output_dir,
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
        self.build_list_widget.load_builds(select_build=selected_branch)
        
    def on_branch_selected(self):
        """Do things you want to do when user selects a branch in the UI"""
        build_dir = self.build_conf.get("unreal.archive_directory")
        self.build_list_widget.project_builds_root = unc_join_path(build_dir, self.project_name)
        self.build_list_widget.load_builds()

    def get_selected_branch(self):
        selected_items = self.branch_list.selectedItems()
        if not selected_items:
            return None
        return selected_items[0].text()

    def focusInEvent(self, a0):
        self.build_list_widget.load_builds()
        return super().focusInEvent(a0)

    def closeEvent(self, event):
        if self.vcs_client:
            self.vcs_client._disconnect()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    window = BuildBridgeWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
