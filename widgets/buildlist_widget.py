from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
)
from PyQt6.QtCore import Qt
import os
from conf.config_manager import ConfigManager
from builder.unreal_builder import UnrealBuilder
from exceptions import InvalidConfigurationError
from publisher.steam.steam_publisher import SteamPublisher


class BuildListWidget(QWidget):
    def __init__(self, project_builds_root: str, parent=None):
        super().__init__(parent)
        self.project_builds_root = project_builds_root

        self.stores_conf = ConfigManager("stores")

        self.setup_ui()
        self.load_builds()

    def setup_ui(self):
        layout = QVBoxLayout()
        self.build_tree = QTreeWidget()  # Use QTreeWidget for nested folders
        self.build_tree.setHeaderHidden(True)  # Hide the header
        self.build_tree.itemSelectionChanged.connect(self.update_button_state)

        button_layout = QHBoxLayout()
        self.open_explorer_button = QPushButton("Open in Explorer")
        self.open_explorer_button.clicked.connect(self.open_in_explorer)
        self.open_explorer_button.setEnabled(False)
        button_layout.addWidget(self.open_explorer_button)

        publish_btn = QPushButton("Publish Selected")
        publish_btn.clicked.connect(self.handle_publish)
        button_layout.addWidget(publish_btn)

        layout.addWidget(self.build_tree)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def load_builds(self, select_build=None, max_depth=3):
        """Load builds into the tree widget, supporting configurable levels of subfolders."""
        self.build_tree.clear()
        if self.project_builds_root and os.path.exists(self.project_builds_root):
            self._add_subfolders(
                self.build_tree,
                self.project_builds_root,
                current_depth=0,
                max_depth=max_depth,
            )

            if select_build:
                items = self.build_tree.findItems(
                    select_build,
                    Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive,
                )
                if items:
                    self.build_tree.setCurrentItem(items[0])
        self.update_button_state()

    def _add_subfolders(self, parent, folder_path, current_depth, max_depth):
        """Recursively add subfolders to the tree widget up to the specified depth."""
        if current_depth >= max_depth:
            return

        for folder in os.listdir(folder_path):
            if folder == "Steam":  # Exclude the "Steam" directory
                continue
            subfolder_path = os.path.join(folder_path, folder)
            if os.path.isdir(subfolder_path):
                item = self._create_tree_item(parent, folder, subfolder_path)
                self._add_subfolders(item, subfolder_path, current_depth + 1, max_depth)

    def _create_tree_item(self, parent, name, path):
        """Helper method to create a tree item with a name and associated path."""
        item = QTreeWidgetItem(parent, [name])
        item.setData(0, Qt.ItemDataRole.UserRole, path)
        return item

    def open_in_explorer(self):
        """Open the selected build directory in Windows Explorer."""
        selected_items = self.build_tree.selectedItems()
        if not selected_items:
            return
        build_path = selected_items[0].data(0, Qt.ItemDataRole.UserRole)
        try:
            os.startfile(build_path)  # Windows-only
        except Exception as e:
            print(e)

    def handle_publish(self):
        selected_items = self.build_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(
                self, "Selection Error", "Please select a build to publish."
            )
            return

        selected_item = selected_items[0]
        selected_path = selected_item.data(0, Qt.ItemDataRole.UserRole)

        has_exe_in_root = any(
            file.endswith(".exe") for file in os.listdir(selected_path)
        )
        first_subfolder = next(
            (os.path.join(selected_path, subfolder) for subfolder in os.listdir(selected_path) if os.path.isdir(os.path.join(selected_path, subfolder))),
            None
        )
        has_exe_in_subfolder = first_subfolder and any(
            file.endswith(".exe") for file in os.listdir(first_subfolder)
        )
        if not has_exe_in_root and not has_exe_in_subfolder:
            QMessageBox.warning(
                self,
                "Invalid Selection",
                "Please select an actual build folder, not an intermediate folder.",
            )
            return

        if not self.stores_conf:
            QMessageBox.warning(
                self,
                "No Publishers",
                "No publishing destinations enabled. Configure in Settings.",
            )
            return

        # TODO: support multiple stores
        if self.stores_conf.get("steam"):
            publisher = SteamPublisher()
            try:
                publisher.publish(build_root=selected_path)
            except InvalidConfigurationError as e:
                QMessageBox.warning(
                    self,
                    "Publishing Error",
                    f"Failed to publish the selected build: {str(e)}",
                )

    def update_button_state(self):
        """Enable/disable buttons based on selection."""
        selected = bool(self.build_tree.selectedItems())
        self.open_explorer_button.setEnabled(selected)
