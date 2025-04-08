from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QFileDialog
)
from PyQt6.QtCore import Qt
import os
from exceptions import InvalidConfigurationError
from core.publisher.steam.steam_publisher import SteamPublisher


class BuildListEntryWidget(QWidget):
    def __init__(self, build_root):
        super().__init__()
        self.build_root = build_root
        self.publish_conf = None

        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        self.label = QLabel(build_root)

        browse_archive_button = QPushButton("Browse")
        browse_archive_button.clicked.connect(self.browse_archive_directory)
        

        self.combo = QComboBox()
        self.combo.addItems(["Steam", "itch.io"])  # Example targets

        self.publish_button = QPushButton("Publish")
        self.edit_button = QPushButton("Edit")

        layout.addWidget(self.label)
        layout.addWidget(self.combo)
        layout.addStretch()
        layout.addWidget(browse_archive_button  )
        layout.addWidget(self.edit_button)
        layout.addWidget(self.publish_button)

        self.setLayout(layout)


    def browse_archive_directory(self):
        try:
            os.startfile(self.build_root)  # Windows-only
        except Exception as e:
            print(e)

    def handle_publish(self):
        if not self.build_root:
            raise InvalidConfigurationError(
                "The build entry widget has no source dir to build."
            )

        has_exe_in_root = any(
            file.endswith(".exe") for file in os.listdir(self.build_root)
        )
        first_subfolder = next(
            (
                os.path.join(self.build_root, subfolder)
                for subfolder in os.listdir(self.build_root)
                if os.path.isdir(os.path.join(self.build_root, subfolder))
            ),
            None,
        )
        has_exe_in_subfolder = first_subfolder and any(
            file.endswith(".exe") for file in os.listdir(first_subfolder)
        )
        if not has_exe_in_root and not has_exe_in_subfolder:
            raise InvalidConfigurationError(f"The build_src provided: {self.build_root} is not a valid application folder.")

        if not self.publish_conf:
            QMessageBox.warning(
                self,
                "No Publishers",
                "No publishing destinations enabled. Configure at least one.",
            )
            return

        # TODO: support multiple stores
        if self.stores_conf.get("steam"):
            publisher = SteamPublisher()
            try:
                publisher.publish(build_root=self.build_root)
            except InvalidConfigurationError as e:
                QMessageBox.warning(
                    self,
                    "Publishing Error",
                    f"Failed to publish the selected build: {str(e)}",
                )


class BuildListWidget(QWidget):
    def __init__(self, builds_dir:str = None):
        super().__init__()
        self.setWindowTitle("Available Builds")
        self.setMinimumSize(600, 400)

        # Scroll area setup
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        # Widget container inside scroll area
        scroll_content = QWidget()
        self.vbox = QVBoxLayout(scroll_content)
        self.vbox.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll_area.setWidget(scroll_content)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll_area)

        # Populate with subdirectory widgets
        self.load_builds(builds_dir)

    def load_builds(self, path):
        if not path:
            return
        if not (os.path.exists(path)):
            return
        for entry in os.listdir(path):
            full_path = os.path.join(path, entry)
            if os.path.isdir(full_path):
                widget = BuildListEntryWidget(entry)
                self.vbox.addWidget(widget)
