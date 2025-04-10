from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QMenu,
    QToolTip,
    QSizePolicy,
    QComboBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
import os

from requests import session

from core.publisher.itch.itch_publisher import ItchPublisher
from database import session_scope
from exceptions import InvalidConfigurationError
from core.publisher.steam.steam_publisher import SteamPublisher
from models import Project, PublishProfile, StoreEnum
from views.dialogs.platform_publish_dialog import PlatformPublishDialog
from views.widgets.steam_config_widget import SteamConfigWidget


class PublishTargetEntry(QWidget):
    store_publishers = {StoreEnum.itch: ItchPublisher, StoreEnum.steam: SteamPublisher}

    def __init__(self, build_root):
        super().__init__()
        self.build_root = build_root
        self.build_id = os.path.basename(build_root)
        self.publish_conf = None

        # Main horizontal layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(15)

        # SINGLE PROJECT SETUP
        with session_scope() as session:
            project = session.query(Project).one_or_none()

            # Left: Build label
            label = f"{project.name} - {self.build_id}"

            if project:
                self.label = QLabel(label)
            else:
                self.label = QLabel(self.build_id)

        self.label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.label.setFixedWidth(120)

        # TODO: Multi-store publish
        self.platform_menu_combo = QComboBox()
        platform_layout = QHBoxLayout()
        platform_layout.addWidget(QLabel("Target Platform:"))
        platform_layout.addWidget(self.platform_menu_combo)
        layout.addLayout(platform_layout)

        self.platform_menu_combo.currentTextChanged.connect(self.on_target_platform_changed)

        for publisher in self.store_publishers:
            self.platform_menu_combo.addItem(publisher.value, publisher)

        # Right-side buttons
        browse_archive_button = QPushButton("Browse")
        browse_archive_button.setFixedHeight(28)
        browse_archive_button.clicked.connect(self.browse_archive_directory)

        self.edit_button = QPushButton("Profile")
        self.edit_button.setFixedHeight(28)
        self.edit_button.clicked.connect(self.edit_publish_profile)

        self.publish_button = QPushButton("Publish")
        self.publish_button.setFixedHeight(28)
        self.publish_button.clicked.connect(self.handle_publish)

        self.publish_button.setToolTip("")

        self.publish_button.setEnabled(self.can_publish())

        # Group buttons to keep them aligned
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        button_layout.addWidget(browse_archive_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.publish_button)

        # Add widgets to main layout
        layout.addWidget(self.label)
        layout.addStretch()  # Push buttons to the right
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def on_target_platform_changed(self):
        self.publish_button.setEnabled(self.can_publish())

    def on_publish_profile_added_or_updated(self):
        self.publish_button.setEnabled(self.can_publish())

    def get_publish_profile_for_store(self, store: StoreEnum, session):
        profile = session.query(PublishProfile).filter_by(store_type=store.value).first()
        return profile

    def can_publish(self) -> bool:
        """Based on selected platform, allows or not to publish by
        enabling/disabling the button if config is not valid"""
        try:

            self.validate()
            with session_scope() as session:
                selected_platform = self.platform_menu_combo.currentData()

                publish_profile_selected_platform = self.get_publish_profile_for_store(selected_platform, session)

                publisher = self.store_publishers[selected_platform]()

                if publish_profile_selected_platform:
                    publisher.validate_publish_profile(publish_profile_selected_platform)
                else:
                    raise InvalidConfigurationError(f"Missing profile for {selected_platform}")
        except InvalidConfigurationError as e:
            self.publish_button.setToolTip(f"Some configuration is missing or invalid: \n\n     {e}")
            print(f"PublisTargetEntryWidget: invlaid configuration: \n\n    {e}.")
            return False
        return True

    def validate(self):
        """Validates basic things like stores selected and that files look like a build (have an .exe inside)."""
        selected_platform = self.platform_menu_combo.currentData()
        print(self)
        if not selected_platform:
           raise InvalidConfigurationError("You must select at least one store from the list.")
        
        if not self.build_root:
            raise InvalidConfigurationError(
                "The build entry widget has no source dir to build to."
            )

        # Ensure there is executable directly in build_root or in first child (version number folder) - Win only
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
            raise InvalidConfigurationError("You must select at least one store from the list.")


    def browse_archive_directory(self):
        try:
            os.startfile(self.build_root)  # Windows-only
        except Exception as e:
            print(e)

    def edit_publish_profile(self):
        sel_platform = self.platform_menu_combo.currentText()

        dialog = PlatformPublishDialog(platform=sel_platform, build_id=self.build_id)
        dialog.profile_changed_signal.connect(self.on_publish_profile_added_or_updated)
        dialog.exec()

    def handle_publish(self):
        # We get here only if button to publish is enabled. And this is enabled only
        # if we have valid conf for the selected store(s).

        # Support only one store now. Maybe queues in the future (or parallel uploads)
        # after validate config we must be sure at lest one platform is selected
        selected_platform = self.platform_menu_combo.currentData()
        publisher = self.store_publishers[selected_platform]()

        print(f"Publishing on {selected_platform}")

        if not publisher:
            QMessageBox.warning(
                self,
                "No Publishers",
                "No publishing destinations enabled. Configure at least one.",
            )
            return

        try:
            publisher.publish(content_dir=self.build_root, build_id=self.build_id)
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

        self.monitored_directory = builds_dir

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

    def refresh_builds(self, new_dir: str = None):
        # allows to set nothing to show nothing.

        if not new_dir or not os.path.isdir(new_dir):
            print(
                "PublishTargetsListWidget: Refreshing with empty new dir. Showing empty"
            )
            self.empty_message_label.setVisible(True)
            return

        print(f"PublishTargetsListWidget: Setting new monitored dir to: {new_dir}")
        self.monitored_directory = new_dir

        if not self.monitored_directory or not os.path.exists(self.monitored_directory):
            print(
                f"PublishTargetsListWidget: No valid build path: {self.monitored_directory}"
            )
            self.empty_message_label.setVisible(True)
            return

        # Clear existing widgets in the layout
        while self.vbox.count():
            child = self.vbox.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        builds_found = False


        # Run through children and see if we want to filter out config dirs
        # Add the rest as entries. This should really be made to use a model
        for entry in sorted(os.listdir(self.monitored_directory)):
            full_path = os.path.join(self.monitored_directory, entry)

            # filtering the store config by name and validating dir all at once yeee
            if os.path.isdir(full_path) and not entry in [
                store.value for store in StoreEnum
            ]:
                widget = PublishTargetEntry(full_path)
                self.vbox.addWidget(widget)
                builds_found = True

        # Show/hide the empty message label
        self.empty_message_label.setVisible(not builds_found)
