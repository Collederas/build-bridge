from ast import List
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QMenu,
    QToolButton,
    QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
import os
from database import SessionFactory, session_scope
from exceptions import InvalidConfigurationError
from core.publisher.steam.steam_publisher import SteamPublisher
from models import StoreEnum
from views.dialogs.steam_publish_profile_dialog import SteamPublishProfileDialog


class PublishTargetEntry(QWidget):
    store_publishers = {StoreEnum.itch: None, StoreEnum.steam: SteamPublisher}

    def __init__(self, build_root):
        super().__init__()
        self.build_root = build_root
        self.build_id = os.path.basename(build_root)
        self.publish_conf = None

        # Main horizontal layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(15)

        # Left: Build label
        self.label = QLabel(self.build_id)
        self.label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.label.setFixedWidth(80)

        # Platform dropdown button
        self.platform_button = QToolButton()
        self.platform_button.setText("Select Platforms")
        self.platform_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.platform_button.setFixedWidth(150)
        self.platform_button.setFixedHeight(28)

        self.platform_menu = QMenu()
        self.platforms = {}
        for name in [StoreEnum.itch.value, StoreEnum.steam.value]:
            action = QAction(name, self)
            action.setCheckable(True)
            action.setChecked(True)
            self.platform_menu.addAction(action)
            self.platforms[name] = action

        self.platform_menu.triggered.connect(self.update_platform_button_text)
        self.platform_button.setMenu(self.platform_menu)
        self.update_platform_button_text()

        # Right-side buttons
        browse_archive_button = QPushButton("Browse")
        browse_archive_button.setFixedHeight(28)
        browse_archive_button.clicked.connect(self.browse_archive_directory)

        self.edit_button = QPushButton("Manage Publish Profile")
        self.edit_button.setFixedHeight(28)
        self.edit_button.clicked.connect(self.edit_publish_profile)

        self.publish_button = QPushButton("Publish")
        self.publish_button.setFixedHeight(28)
        self.publish_button.clicked.connect(self.handle_publish)

        # Group buttons to keep them aligned
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        button_layout.addWidget(browse_archive_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.publish_button)

        # Add widgets to main layout
        layout.addWidget(self.label)
        layout.addWidget(self.platform_button)
        layout.addStretch()  # Push buttons to the right
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def edit_publish_profile(self):
        session = SessionFactory()
        dialog = SteamPublishProfileDialog(session=session, build_id=self.build_id)
        dialog.exec()

    def update_platform_button_text(self):
        selected = [
            name for name, action in self.platforms.items() if action.isChecked()
        ]
        if selected:
            text = ", ".join(selected)
            if len(text) > 20:
                text = text[:17] + "..."
            self.platform_button.setText(text)
        else:
            self.platform_button.setText("Select Platforms")

    def get_selected_platforms(self):
        return [name for name, action in self.platforms.items() if action.isChecked()]

    def browse_archive_directory(self):
        try:
            os.startfile(self.build_root)  # Windows-only
        except Exception as e:
            print(e)

    def handle_publish(self):
        # Support only one store now. Maybe queues in the future (or parallel uploads)

        if not self.build_root:
            raise InvalidConfigurationError(
                "The build entry widget has no source dir to build."
            )

        # Ensure there is executable - Win only
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
            raise InvalidConfigurationError(
                f"The build_src provided: {self.build_root} is not a valid application folder."
            )

        # Check we have a valid store publisher. For now we only support steam
        selected_platforms = self.get_selected_platforms()
        if StoreEnum.itch.value in selected_platforms:
            QMessageBox.warning(self, "Unsupported Store", f"{StoreEnum.itch.value} is not (yet!) supported!")

        if StoreEnum.steam.value in selected_platforms:
            publisher = self.store_publishers.get(StoreEnum.steam)()

        if not publisher:
            QMessageBox.warning(
                self,
                "No Publishers",
                "No publishing destinations enabled. Configure at least one.",
            )
            return

        try:
            publisher.publish(content_dir=self.build_id)
        except InvalidConfigurationError as e:
            QMessageBox.warning(
                self,
                "Publishing Error",
                f"Failed to publish the selected build: {str(e)}",
            )


class PublishTargetsListWidget(QWidget):
    def __init__(self, builds_dir: str = None):
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

        # Message label for empty builds
        self.empty_message_label = QLabel("No builds available")
        self.empty_message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_message_label.setVisible(False)
        main_layout.addWidget(self.empty_message_label)

        # Populate with subdirectory widgets
        self.refresh_builds(builds_dir)

    def refresh_builds(self, path):
        if not path or not os.path.exists(path):
            print(f"No build path: {path}")
            self.empty_message_label.setVisible(True)
            return

        # Clear existing widgets in the layout
        while self.vbox.count():
            child = self.vbox.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        builds_found = False
        for entry in sorted(os.listdir(path)):
            full_path = os.path.join(path, entry)
            print(f"Checking builds in {full_path}")


            # Exclude store config directories
            if os.path.isdir(full_path) and not entry in [store.value for store in StoreEnum]:
                widget = PublishTargetEntry(full_path)
                self.vbox.addWidget(widget)
                builds_found = True

        # Show or hide the empty message label
        self.empty_message_label.setVisible(not builds_found)
