import os

from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QSizePolicy,
    QComboBox,
    QWidget,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QCheckBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from build_bridge.models import ItchPublishProfile, SteamPublishProfile, StoreEnum
from build_bridge.core.publisher.itch.itch_publisher import ItchPublisher
from build_bridge.database import SessionFactory
from build_bridge.exceptions import InvalidConfigurationError
from build_bridge.core.publisher.steam.steam_publisher import SteamPublisher
from build_bridge.models import Project, PublishProfile, StoreEnum
from build_bridge.views.dialogs.publish_profile_dialog import PublishProfileDialog

# Import the styles
from build_bridge.style.app_style import (
    ENTRY_STYLE,
    BUILD_LABEL_STYLE,
    PLATFORM_LABEL_STYLE,
    REFRESH_BUTTON_STYLE,
    BROWSE_BUTTON_STYLE,
    EDIT_BUTTON_STYLE,
    PUBLISH_BUTTON_STYLE,
    EMPTY_MESSAGE_STYLE
)

class PublishProfileListWidget(QWidget):
    def __init__(self, builds_dir: str = None):
        super().__init__()
        # OWNS SESSION FOR ALL OPERATIONS ON PUBLISH PROFILES.
        # It starts here and gets passed to each Entry widget.
        # Then each entry widget passes this down further to its related dialogs.
        self.session = SessionFactory()

        self.setWindowTitle("Available Builds")

        # Store the directory path internally - set the initial value
        self.monitored_directory = builds_dir

        # Set a more compact initial size and minimum size
        self.setGeometry(100, 100, 600, 400)
        self.setMinimumSize(500, 300)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # --- Refresh Button ---
        self.refresh_button = QPushButton("🔄 Refresh")
        self.refresh_button.setToolTip(
            "Rescan the currently monitored build directory for changes"
        )
        self.refresh_button.clicked.connect(self.refresh_builds)
        self.refresh_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.refresh_button.setFixedWidth(100)  # Fixed width to prevent stretching
        main_layout.addWidget(self.refresh_button)
        # --- End Refresh Button ---

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVisible(True)  # Always visible
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.scroll_area.setMinimumHeight(100)  # Ensure scroll area doesn't disappear

        self.scroll_content = QWidget()
        self.vbox = QVBoxLayout(self.scroll_content)
        self.vbox.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.vbox.setContentsMargins(0, 0, 0, 0)
        self.vbox.setSpacing(5)
        self.scroll_area.setWidget(self.scroll_content)

        self.empty_message_label = QLabel("No builds available.")
        self.empty_message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_message_label.setContentsMargins(10, 20, 10, 20)
        self.empty_message_label.setVisible(True)
        self.empty_message_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        main_layout.addWidget(self.scroll_area)
        main_layout.addWidget(self.empty_message_label)
        # --- End Scroll Area Setup ---

        self.refresh_builds()

    def refresh_builds(self, new_dir: str = None):
        """
        Refreshes the list of builds displayed by scanning the monitored directory.
        Clears previous entries and shows/hides the 'No builds' message.
        """
        print(f"=====NEW DIR: {new_dir}=====")
        
        # Update monitored_directory only if a new valid directory is provided
        if new_dir is not None and os.path.isdir(new_dir):
            print(f"  - Updating monitored directory to: {new_dir}")
            self.monitored_directory = new_dir
        else:
            print(f"  - Keeping existing monitored directory: {self.monitored_directory}")

        # Use the current monitored_directory for scanning
        dir_to_scan = self.monitored_directory
        print(f"  - Refreshing based on directory: {dir_to_scan}")

        # --- 1. Clear existing widgets ---
        while self.vbox.count():
            child = self.vbox.takeAt(0)
            if child.widget():
                print(f"  - Clearing widget: {child.widget()}")
                child.widget().deleteLater()

        # --- 2. Check if the directory is valid ---
        is_valid_dir = False
        if dir_to_scan and os.path.isdir(dir_to_scan):
            is_valid_dir = True
            print(f"  - Directory '{dir_to_scan}' is valid.")
        else:
            print(f"  - Directory '{dir_to_scan}' is invalid or None.")
            self.empty_message_label.setText(
                "Builds directory not set." if not dir_to_scan else f"Directory not found:\n{dir_to_scan}"
            )

        # If directory is invalid, show empty state and return
        if not is_valid_dir:
            self.empty_message_label.setVisible(True)
            print("  - Showing empty message (invalid dir), returning.")
            return

        # --- 3. Populate builds if directory is valid ---
        builds_found = False
        try:
            entries = sorted(os.listdir(dir_to_scan))
            print(f"  - Scanning entries: {entries}")

            for entry in entries:
                full_path = os.path.join(dir_to_scan, entry)
                is_config_dir = any(entry == store.value for store in StoreEnum)

                if os.path.isdir(full_path) and not is_config_dir:
                    print(f"    - Found potential build directory: {entry}")
                    widget = PublishProfileEntry(full_path, session=self.session)
                    self.vbox.addWidget(widget)
                    builds_found = True
                elif is_config_dir:
                    print(f"    - Skipping config directory: {entry}")
                else:
                    print(f"    - Skipping non-directory entry: {entry}")

        except OSError as e:
            print(f"  - Error listing directory '{dir_to_scan}': {e}")
            self.empty_message_label.setText(f"Error reading directory:\n{e}")
            builds_found = False
        except Exception as e:
            print(f"  - Unexpected error processing directory '{dir_to_scan}': {e}")
            self.empty_message_label.setText("An unexpected error occurred.")
            builds_found = False

        self.vbox.addStretch(1)

        # --- 4. Set final visibility ---
        if builds_found:
            self.empty_message_label.setVisible(False)
        else:
            if is_valid_dir:
                self.empty_message_label.setText("No builds available in the monitored directory.")
            self.empty_message_label.setVisible(True)


class PublishProfileEntry(QWidget):
    store_publishers = {StoreEnum.itch: ItchPublisher, StoreEnum.steam: SteamPublisher}

    def __init__(self, build_root, session):
        super().__init__()
        self.build_root = build_root
        self.publish_profile = None
        self.session = session

        if build_root and os.path.exists(build_root):
            self.build_id = os.path.basename(build_root)
        else:
            self.build_id = "Invalid Path"
            print(
                f"Warning: Invalid build_root passed to PublishTargetEntry: {build_root}"
            )


        # Use a responsive layout with QVBoxLayout and QHBoxLayout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 8, 15, 8)
        self.main_layout.setSpacing(10)

        # First row: Label and Platform Selector with Checkbox
        self.top_row = QHBoxLayout()
        self.top_row.setSpacing(25)

        # Build Label
        project_name_str = "Unknown Project"
        try:
            project = session.query(Project).one_or_none()
            if project:
                project_name_str = project.name
        except Exception as e:
            print(f"Error fetching project name: {e}")

        display_name_font = QFont()
        display_name_font.setBold(True)
        self.display_name_label = QLabel(f"{project_name_str} - {self.build_id}")
        self.display_name_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.display_name_label.setWordWrap(True)
        self.display_name_label.setFont(display_name_font)
        self.top_row.addWidget(self.display_name_label)

        # Platform Selector with Checkbox
        self.platform_widget = QWidget()
        self.platform_layout = QHBoxLayout(self.platform_widget)
        self.platform_layout.setContentsMargins(0, 0, 0, 0)
        self.platform_layout.setSpacing(5)

        self.store_type_label = QLabel("Target Platform:")
        self.store_type_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.platform_layout.addWidget(self.store_type_label)

        self.store_type_combo = QComboBox()
        self.store_type_combo.setMinimumWidth(100)
        self.store_type_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        for store_enum in self.store_publishers.keys():
            self.store_type_combo.addItem(str(store_enum.value), store_enum)
        self.store_type_combo.setToolTip("Select the target platform for publishing this build")
        self.platform_layout.addWidget(self.store_type_combo)

        # Add the checkbox directly after the dropdown
        self.playtest_checkbox = QCheckBox("Publish Playtest")
        self.playtest_checkbox.setToolTip("Publish to Steam Playtest branch instead of the main app")
        self.playtest_checkbox.setVisible(False)
        self.playtest_checkbox.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.platform_layout.addWidget(self.playtest_checkbox)
        self.playtest_checkbox.stateChanged.connect(self.update_publish_button_enabled)

        # Prevent the platform layout from stretching unnecessarily
        self.platform_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.top_row.addWidget(self.platform_widget)

        # Add stretch to the end of the row to push everything to the left
        self.top_row.addStretch(1)

        self.main_layout.addLayout(self.top_row)

        # Second row: Buttons
        self.bottom_row = QHBoxLayout()
        self.bottom_row.setSpacing(10)

        self.bottom_row.addStretch(1)

        # Buttons
        browse_archive_button = QPushButton("Browse")
        browse_archive_button.setToolTip(f"Open build folder:\n{self.build_root}")
        browse_archive_button.setFixedHeight(28)
        browse_archive_button.setFixedWidth(70)
        browse_archive_button.clicked.connect(self.browse_archive_directory)
        self.bottom_row.addWidget(browse_archive_button)

        self.edit_button = QPushButton("Profile")
        self.edit_button.setToolTip("Edit publish profile for the selected target platform")
        self.edit_button.setFixedHeight(28)
        self.edit_button.setFixedWidth(70)
        self.edit_button.clicked.connect(self.edit_publish_profile)
        self.bottom_row.addWidget(self.edit_button)

        self.publish_button = QPushButton("Publish")
        self.publish_button.setFixedHeight(28)
        self.publish_button.setFixedWidth(70)
        self.publish_button.clicked.connect(self.handle_publish)
        self.publish_button.setToolTip("")
        self.bottom_row.addWidget(self.publish_button)

        self.main_layout.addLayout(self.bottom_row)
        self.setLayout(self.main_layout)

        # Connect signals after widgets are created
        self.store_type_combo.currentIndexChanged.connect(self.on_store_changed)

        # Initial state check for publish button
        self.on_store_changed()

    def update_publish_button_enabled(self):
        self.publish_button.setEnabled(self.can_publish())

    def on_store_changed(self):
        selected_store_enum_value = self.store_type_combo.currentData()
        is_steam = (selected_store_enum_value == StoreEnum.steam)

        if is_steam:
            self.playtest_checkbox.setVisible(True)
        else:
            self.playtest_checkbox.setVisible(False)
            self.playtest_checkbox.setChecked(False)

        self.update_publish_profile()
        self.update_publish_button_enabled()

    def on_publish_profile_added_or_updated(self):
        self.update_publish_profile()
        self.update_publish_button_enabled()

    def update_publish_profile(self):
        selected_store_enum = self.store_type_combo.currentData()

        if selected_store_enum is None:
            return

        existing_publish_profile = (
            self.session.query(PublishProfile)
            .filter_by(store_type=selected_store_enum.value, build_id=self.build_id)
            .first()
        )
        
        if existing_publish_profile:
            self.publish_profile = existing_publish_profile

        if not existing_publish_profile:
            project = self.session.query(Project).one_or_none()
            store_model_map = {
                StoreEnum.itch: ItchPublishProfile,
                StoreEnum.steam: SteamPublishProfile
            }
            self.publish_profile = store_model_map[selected_store_enum](
                project_id=project.id,
                build_id=self.build_id,
                store_type=selected_store_enum,
            )

    def can_publish(self) -> bool:
        selected_platform_enum = self.store_type_combo.currentData()

        try:
            self.validate_build_content()

            publisher_class = self.store_publishers.get(selected_platform_enum)
            if not publisher_class:
                raise InvalidConfigurationError(
                    f"No publisher implementation found for {selected_platform_enum.value}"
                )
            
            publisher_instance = None
            if selected_platform_enum == StoreEnum.steam:
                publish_playtest_value = self.playtest_checkbox.isChecked()
                publisher_instance = publisher_class(
                    publish_profile=self.publish_profile,
                    publish_playtest=publish_playtest_value
                )
            else:
                publisher_instance = publisher_class(
                    publish_profile=self.publish_profile
                )

            publisher_instance.validate_publish_profile()

            self.publish_button.setToolTip(
                f"Publish build '{self.build_id}' to {selected_platform_enum.value}"
            )
            return True

        except InvalidConfigurationError as e:
            self.publish_button.setToolTip(f"Cannot publish: {e}")
            return False
        except Exception as e:
            self.publish_button.setToolTip(f"Unexpected validation error: {e}")
            print(f"Unexpected validation error: {e}")
            return False

    def validate_build_content(self):
        if not self.build_root or not os.path.isdir(self.build_root):
            self.publish_button.setToolTip(
                f"Build directory is invalid or not found:\n{self.build_root}"
            )
            return False

        if not self.build_root or not os.path.isdir(self.build_root):
            raise InvalidConfigurationError("Build directory path is invalid.")

        try:
            has_exe_in_root = any(
                f.lower().endswith(".exe")
                for f in os.listdir(self.build_root)
                if os.path.isfile(os.path.join(self.build_root, f))
            )

            first_subfolder_path = None
            for item in os.listdir(self.build_root):
                full_item_path = os.path.join(self.build_root, item)
                if os.path.isdir(full_item_path):
                    first_subfolder_path = full_item_path
                    break

            has_exe_in_subfolder = False
            if first_subfolder_path:
                has_exe_in_subfolder = any(
                    f.lower().endswith(".exe")
                    for f in os.listdir(first_subfolder_path)
                    if os.path.isfile(os.path.join(first_subfolder_path, f))
                )

            if not has_exe_in_root and not has_exe_in_subfolder:
                raise InvalidConfigurationError(
                    "Build folder or its first subfolder does not contain an executable (.exe)."
                )

        except OSError as e:
            raise InvalidConfigurationError(
                f"Error accessing build directory content: {e}"
            )

    def browse_archive_directory(self):
        if self.build_root and os.path.isdir(self.build_root):
            try:
                if os.name == "nt":
                    os.startfile(self.build_root)
                else:
                    QMessageBox.warning(self, "Unsupported OS", "Unsupported OS")
                    return
            except Exception as e:
                print(f"Error opening directory {self.build_root}: {e}")
                QMessageBox.warning(
                    self,
                    "Error",
                    f"Could not open directory:\n{self.build_root}\n\nError: {e}",
                )
        else:
            QMessageBox.warning(
                self,
                "Error",
                f"Build directory not found or invalid:\n{self.build_root}",
            )

    def edit_publish_profile(self):
        selected_platform_enum = self.store_type_combo.currentData()
        if selected_platform_enum is None:
            QMessageBox.information(
                self,
                "Select Platform",
                "Please select a target platform before editing its profile.",
            )
            return

        edit_dialog = PublishProfileDialog(
            session=self.session, publish_profile=self.publish_profile
        )
        try:
            pass
        except TypeError:
            pass
        edit_dialog.profile_changed_signal.connect(self.on_publish_profile_added_or_updated)
        edit_dialog.exec()

    def handle_publish(self):
        selected_store_enum = self.store_type_combo.currentData()
        if selected_store_enum is None:
            QMessageBox.warning(self, "Error", "No target platform selected.")
            return

        publisher_class = self.store_publishers.get(selected_store_enum)
        if not publisher_class:
            QMessageBox.critical(
                self, "Error", f"No publisher found for {selected_store_enum.value}"
            )
            return

        publisher_instance = None
        try:
            if selected_store_enum == StoreEnum.steam:
                publish_playtest_value = self.playtest_checkbox.isChecked()
                publisher_instance = publisher_class(
                    self.publish_profile,
                    publish_playtest=publish_playtest_value
                )
                print(f"Attempting to publish build '{self.build_id}' to Steam (Playtest: {publish_playtest_value})...")
            else:
                publisher_instance = publisher_class(self.publish_profile)
                print(f"Attempting to publish build '{self.build_id}' to {selected_store_enum}...")

            publisher_instance.publish(content_dir=self.build_root)

        except InvalidConfigurationError as e:
            QMessageBox.warning(
                self,
                "Publishing Error",
                f"Failed to publish '{self.build_id}' to {selected_store_enum.value}:\n\n{str(e)}",
            )
        except NotImplementedError:
            QMessageBox.critical(
                self,
                "Not Implemented",
                f"Publishing for {selected_store_enum.value} is not yet implemented.",
            )
        except Exception as e:
            print(f"Error during publish execution: {e}")
            QMessageBox.critical(
                self,
                "Publishing Failed",
                f"An unexpected error occurred while publishing to {selected_store_enum.value}:\n\n{str(e)}",
            )

    def closeEvent(self, a0):
        self.session.close()
        return super().closeEvent(a0)