from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget
from PyQt6.QtCore import Qt
import os


class BuildListWidget(QWidget):
    def __init__(self, build_dir="C:/Builds", parent=None):
        super().__init__(parent)
        self.build_dir = build_dir
        self.setup_ui()
        self.load_builds()

    def setup_ui(self):
        layout = QVBoxLayout()
        self.build_list = QListWidget()  # Publicly accessible
        layout.addWidget(self.build_list)
        self.setLayout(layout)

    def load_builds(self, select_build=None):
        self.build_list.clear()
        if os.path.exists(self.build_dir):
            builds = [d for d in os.listdir(self.build_dir) if os.path.isdir(os.path.join(self.build_dir, d))]
            self.build_list.addItems(builds)
            if select_build:
                items = self.build_list.findItems(select_build, Qt.MatchFlag.MatchExactly)
                if items:
                    self.build_list.setCurrentItem(items[0])