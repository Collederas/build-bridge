from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QHBoxLayout, QPushButton, QMessageBox
from PyQt6.QtCore import Qt
import os
from app_config import ConfigManager
from builder.unreal_builder import UnrealBuilder
from publisher.steam.steam_publisher import SteamPublisher


class BuildListWidget(QWidget):
    def __init__(self, build_dir:str, parent=None):
        super().__init__(parent)
        self.build_dir = build_dir

        self.stores_conf = ConfigManager("stores")

        self.setup_ui()
        self.load_builds()

    def setup_ui(self):
        layout = QVBoxLayout()
        self.build_list = QListWidget()  # Publicly accessible
        self.build_list.itemSelectionChanged.connect(self.update_button_state)

        button_layout = QHBoxLayout()
        self.open_explorer_button = QPushButton("Open in Explorer")
        self.open_explorer_button.clicked.connect(self.open_in_explorer)
        self.open_explorer_button.setEnabled(False)
        button_layout.addWidget(self.open_explorer_button)

        publish_btn = QPushButton("Publish Selected")
        publish_btn.clicked.connect(self.handle_publish)
        button_layout.addWidget(publish_btn)
        
        layout.addWidget(self.build_list)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def set_build_dir(self, build_dir: str):
        self.build_dir = build_dir

    def load_builds(self, select_build=None):
        self.build_list.clear()
        if self.build_dir and os.path.exists(self.build_dir):
            builds = [d for d in os.listdir(self.build_dir) if os.path.isdir(os.path.join(self.build_dir, d))]
            self.build_list.addItems(builds)
            if select_build:
                items = self.build_list.findItems(select_build, Qt.MatchFlag.MatchExactly)
                if items:
                    self.build_list.setCurrentItem(items[0])
        self.update_button_state()

    def open_in_explorer(self):
        """Open the selected build directory in Windows Explorer."""
        selected_items = self.build_list.selectedItems()
        if not selected_items:
            return
        build_name = selected_items[0].text()
        build_path = os.path.join(self.build_dir, build_name)
        try:
            os.startfile(build_path)  # Windows-only
        except Exception as e:
            print(e)

    def handle_publish(self):
        selected_items = self.build_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(
                self, "Selection Error", "Please select a build to publish."
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
            publisher.publish(build_path=self.build_dir)

    def update_button_state(self):
        """Enable/disable buttons based on selection."""
        selected = bool(self.build_list.selectedItems())
        self.open_explorer_button.setEnabled(selected)