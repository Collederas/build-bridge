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
from PyQt6.QtCore import Qt

from app_config import ConfigManager
from builder.build_dialog import BuildWindowDialog
from builder.buildlist_widget import BuildListWidget
from builder.unreal_builder import (
    EngineVersionError,
    ProjectFileNotFoundError,
    UnrealBuilder,
    UnrealEngineNotInstalledError,
)
from dialogs.settings import SettingsDialog
from publisher.steam.steam_publisher import SteamPublisher
from utils.paths import unc_join_path
import vcs
from vcs.p4client import P4Client
from vcs.vcsbase import MissingConfigException


class BuildBridgeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Build Bridge")
        self.setWindowIcon(QIcon("icons/buildbridge.ico"))
        self.setGeometry(100, 100, 500, 400)  # Slightly wider window

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
        builds_layout.addWidget(QLabel("Existing Builds:"))

        # Initialize build_list_widget without a directory initially
        self.build_list_widget = BuildListWidget(None, self)
        self.build_list_widget.setMinimumHeight(100)
        builds_layout.addWidget(self.build_list_widget)

        main_layout.addWidget(builds_widget)

        if self.vcs_client:
            self.refresh_branches()

        # Connect branch selection to update builds
        self.branch_list.itemSelectionChanged.connect(self.update_build_list)

        if self.vcs_client:
            self.refresh_branches()

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.vcs_client = P4Client()
            self.refresh_branches()

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
        selected_items = self.branch_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(
                self, "Selection Error", "Please select a branch to build."
            )
            return
        selected_branch = selected_items[0].text()
        if selected_branch == "No release branches found.":
            QMessageBox.warning(self, "Selection Error", "No valid branch selected.")
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

        try:

            # TODO: Either app.py owns all configs or the various classes (VCSClients, Builders, etc.) do. Like this is a mess

            # We have opinions: we want to enforce structure where User can pick a Build dir
            # but we use the VCS branch name (or tag/label, when that is supported) to allow
            # having multiple builds. User might want to keep previous versions. This allows to
            # neatly have all versions of the project's build inside the same root dir.
            build_conf = ConfigManager("build")
            build_dest = self.get_build_dir(build_conf)

            if os.path.exists(build_dest):
                response = QMessageBox.question(
                    self,
                    "Build Conflict",
                    f"A build already exists at:\n{build_dest}\n\nDo you want to proceed and overwrite it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if response == QMessageBox.StandardButton.No:
                    return
                try:
                    shutil.rmtree(build_dest)
                except Exception as e:
                    QMessageBox.critical(
                        self,
                        "Cleanup Error",
                        f"Failed to delete existing build directory:\n{str(e)}",
                    )
                    return
            
            unreal_builder = UnrealBuilder(
                root_directory=self.vcs_client.get_workspace_root(),
                release_id=selected_branch.strip("//")
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
                f"Unreal Engine not found at: {unreal_builder.ue_base_path}",
            )
            return

        dialog = BuildWindowDialog(unreal_builder, parent=self)
        dialog.exec()
        self.build_list_widget.load_builds(select_build=selected_branch)

    def update_build_list(self):
        """Update the build list based on the selected branch."""
        build_dir = self.get_build_dir(ConfigManager("build"))
        self.build_list_widget.set_build_dir(build_dir)
        self.build_list_widget.load_builds()
    
    def get_build_dir(self, build_conf):
        """Return the build directory for the selected branch, or None if no branch is selected."""
        selected_items = self.branch_list.selectedItems()
        if not selected_items:
            return None  # No branch selected, no build dir. They are tied
        selected_branch = selected_items[0].text()
        if selected_branch == "No release branches found.":
            return None
        build_dir = build_conf.get("unreal").get("archive_directory")
        return unc_join_path(build_dir, selected_branch)

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
