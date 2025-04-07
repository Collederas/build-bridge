from pathlib import Path
import re
import sys
import shutil
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QMessageBox,
    QMenu,
)
from PyQt6.QtGui import QIcon


from core.vcs.p4client import P4Client
from core.vcs.vcsbase import MissingConfigException
from database import initialize_database
from views.dialogs.build_dialog import BuildWindowDialog
from views.widgets.build_targets_widget import BuildTargetListWidget
from views.widgets.build_list_widget import BuildListWidget
from core.builder.unreal_builder import (
    EngineVersionError,
    ProjectFileNotFoundError,
    UnrealBuilder,
    UnrealEngineNotInstalledError,
)
from views.dialogs.settings_dialog import SettingsDialog
from utils.paths import unc_join_path


class BuildBridgeWindow(QMainWindow):
    vcs_clients = (P4Client,)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Build Bridge")
        self.setWindowIcon(QIcon("icons/buildbridge.ico"))
        self.setGeometry(100, 100, 500, 400)

        self.vcs_client = None

        # Extend with switch logic based on conf
        try:
            self.vcs_client = self.vcs_clients[0]()
        except MissingConfigException:
            self.vcs_client = None
        except ConnectionError:
            QMessageBox.warning(
                self,
                "Wrong VCS Configuration",
                "VCS is misconfigured. Check details in File->Settings->VCS",
            )

        self.project_name = None

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
        build_target_widget = BuildTargetListWidget(self)
        main_layout.addWidget(build_target_widget)

        # Builds Section
        builds_widget = QWidget()
        builds_layout = QVBoxLayout(builds_widget)
        builds_layout.addWidget(QLabel("Available Builds:"))

        # Initialize build_list_widget
 
        self.build_list_widget = BuildListWidget()


        self.build_list_widget.setMinimumHeight(100)
        builds_layout.addWidget(self.build_list_widget)

        main_layout.addWidget(builds_widget)

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
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
                "Ensure this is a valid regex that can extrapolate the release name from your"
                " branch naming convention.",
            )
            return

        project_build_dir_root = Path(unc_join_path(builds_root, self.project_name))
        this_release_output_dir = (
            project_build_dir_root
            / release_name
            / self.build_conf.get("unreal.build_type")
        )
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
    initialize_database()

    app = QApplication(sys.argv)
    window = BuildBridgeWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
