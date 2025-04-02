import sys
import os

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
from vcs.p4client import P4Client
from vcs.vcsbase import MissingConfigException


class BuildBridgeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Build Bridge")
        self.setWindowIcon(QIcon("icons/buildbridge.ico"))
        self.setGeometry(100, 100, 400, 300)

        try:
            self.vcs_client = P4Client()
        except MissingConfigException as e:
            QMessageBox.warning(
                self,
                "Missing VCS Configuration",
                "VCS is not configured. You can set it up in File->Settings->VCS",
            )
        except ConnectionError:
            QMessageBox.warning(
                self,
                "Wrong VCS Configuration",
                "VCS is misconfigured. Check details in File->Settings->VCS",
            )
            self.vcs_client = None

        # TODO: Move to config
        self.build_dir = "C:/Builds"

        self.publishers = {}
        self.build_list_widget = None

        self.init_ui()

    def init_ui(self):
        menu_bar = self.menuBar()
        # Creating menus using a QMenu object
        file_menu = QMenu("&File", self)
        menu_bar.addMenu(file_menu)
        settings_action = file_menu.addAction("Settings")
        settings_action.triggered.connect(self.open_settings_dialog)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        layout.addWidget(QLabel("Release Branches:"))
        self.branch_list = QListWidget()
        layout.addWidget(self.branch_list)

        button_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh Branches")
        refresh_btn.clicked.connect(self.refresh_branches)
        button_layout.addWidget(refresh_btn)
        build_btn = QPushButton("Build Selected")
        build_btn.clicked.connect(self.trigger_build)
        button_layout.addWidget(build_btn)

        layout.addWidget(QLabel("Existing Builds:"))
        self.build_list_widget = BuildListWidget(self.build_dir, self)
        layout.addWidget(self.build_list_widget)

        publish_btn = QPushButton("Publish Selected")
        publish_btn.clicked.connect(self.handle_publish)
        button_layout.addWidget(publish_btn)
        layout.addLayout(button_layout)

        if self.vcs_client:
            self.refresh_branches()

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            vcs_config, publisher_configs = dialog.get_configs()
            self.vcs_config = vcs_config
            self.vcs_client = P4Client()
            self.publishers.clear()

            for store_conf in publisher_configs:
                print(store_conf)
                if store_conf["Steam"]["enabled"]:
                    publisher = SteamPublisher()
                    self.publishers["Steam"] = publisher
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

        # Switch to the selected branch if we're not there already
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

        # Determine the local project path
        try:
            vcs_root = self.vcs_client.get_workspace_root()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Project Path Error",
                f"Could not find project path for '{selected_branch}':\n\n{str(e)}\n\n"
                "Ensure the branch contains a valid Unreal project.",
            )
            return

        try:

            build_dest = unc_join_path(self.build_dir, selected_branch)
            # Check if build directory already exists
            if os.path.exists(build_dest):
                response = QMessageBox.question(
                    self,
                    "Build Conflict",
                    f"A build already exists at:\n{build_dest}\n\nDo you want to proceed and overwrite it? This will delete the existing build directory.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if response == QMessageBox.StandardButton.No:
                    return  # Cancel and return to main window
                # Proceed with cleanup
                import shutil

                try:
                    shutil.rmtree(build_dest)
                except Exception as e:
                    QMessageBox.critical(
                        self,
                        "Cleanup Error",
                        f"Failed to delete existing build directory:\n{str(e)}",
                    )
                    return

            # Feed the VCS root to the builder and let it find the uproject
            # It will do all sorts of validations to ensure we can actually
            # build the project and scream if prerequisites are not met.
            unreal_builder = UnrealBuilder(
                root_directory=vcs_root, build_dest=build_dest
            )
        except ProjectFileNotFoundError as e:
            QMessageBox.critical(
                self,
                "Project File Error",
                f"Project file not found: {str(e)}",
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
                self, f"Unreal Engine Not Found at: {unreal_builder.ue_base_path}"
            )

            return

        dialog = BuildWindowDialog(unreal_builder, parent=self)
        dialog.exec()

        self.build_list_widget.load_builds(select_build=selected_branch)

    def handle_publish(self):
        selected_items = self.build_list_widget.build_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(
                self, "Selection Error", "Please select a build to publish."
            )
            return
        
        if not self.publishers:
            QMessageBox.warning(
                self,
                "No Publishers",
                "No publishing destinations enabled. Configure in Settings.",
            )
            return
        for publisher in self.publishers.items():
            publisher.publish()

    def focusInEvent(self, a0):
        self.build_list_widget.load_builds()
        return super().focusInEvent(a0)

    def closeEvent(self, event):
        self.vcs_client._disconnect()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    window = BuildBridgeWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
