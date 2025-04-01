import os
import logging
from PyQt6.QtWidgets import QListWidget, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox
from PyQt6.QtCore import Qt

from publisher.publisher_factory import PublisherFactory

logger = logging.getLogger(__name__)

class BuildListWidget(QWidget):
    def __init__(self, build_dir="C:/Builds", parent=None):
        super().__init__(parent)
        self.build_dir = build_dir
        self.setup_ui()
        self.load_builds()

    def setup_ui(self):
        layout = QVBoxLayout()

        self.build_list = QListWidget()
        self.build_list.itemSelectionChanged.connect(self.update_button_states)
        layout.addWidget(self.build_list)

        button_layout = QHBoxLayout()
        self.open_explorer_button = QPushButton("Open in Explorer")
        self.open_explorer_button.clicked.connect(self.open_in_explorer)
        self.open_explorer_button.setEnabled(False)
        button_layout.addWidget(self.open_explorer_button)

        self.store_selector = QComboBox()
        self.store_selector.addItems(["Steam"])  # Add more stores later (e.g., "Epic")
        button_layout.addWidget(self.store_selector)

        self.publish_button = QPushButton("Publish")
        self.publish_button.clicked.connect(self.open_publish_dialog)
        self.publish_button.setEnabled(False)
        button_layout.addWidget(self.publish_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def load_builds(self, select_build=None):
        """Populate the build list with directories in build_dir."""
        self.build_list.clear()
        if os.path.exists(self.build_dir):
            for item in os.listdir(self.build_dir):
                if os.path.isdir(os.path.join(self.build_dir, item)):
                    self.build_list.addItem(item)
            if select_build:
                items = self.build_list.findItems(select_build, Qt.MatchFlag.MatchExactly)
                if items:
                    items[0].setSelected(True)
        else:
            self.build_list.addItem("No builds found.")
        logger.info(f"Loaded builds from {self.build_dir}")
        self.update_button_states()

    def update_button_states(self):
        """Enable/disable buttons based on selection."""
        selected = bool(self.build_list.selectedItems())
        self.open_explorer_button.setEnabled(selected)
        self.publish_button.setEnabled(selected)

    def open_in_explorer(self):
        """Open the selected build directory in Windows Explorer."""
        selected_items = self.build_list.selectedItems()
        if not selected_items:
            return
        build_name = selected_items[0].text()
        build_path = os.path.join(self.build_dir, build_name)
        try:
            os.startfile(build_path)  # Windows-only
            logger.info(f"Opened Explorer at {build_path}")
        except Exception as e:
            logger.error(f"Explorer open failed: {str(e)}", exc_info=True)

    def open_publish_dialog(self):
        """Open the publish dialog for the selected build."""
        selected_items = self.build_list.selectedItems()
        if not selected_items:
            return
        build_name = selected_items[0].text()
        build_path = os.path.join(self.build_dir, build_name)
        store_name = self.store_selector.currentText()
        try:
            publisher = PublisherFactory.get_publisher(store_name, build_path)
            if not publisher.config.get("app_id"):  # Check if config exists
                if not publisher.configure(self):
                    return
            publisher.publish(self)
        except Exception as e:
            logger.error(f"Publish to {store_name} failed: {str(e)}", exc_info=True)

    def get_selected_build_path(self):
        """Return the full path of the selected build."""
        selected_items = self.build_list.selectedItems()
        if selected_items:
            return os.path.join(self.build_dir, selected_items[0].text())
        return None