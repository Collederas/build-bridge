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
)
from PyQt6.QtCore import Qt

from build_bridge.models import ItchPublishProfile, SteamPublishProfile, StoreEnum

from build_bridge.core.publisher.itch.itch_publisher import ItchPublisher
from build_bridge.database import SessionFactory
from build_bridge.exceptions import InvalidConfigurationError
from build_bridge.core.publisher.steam.steam_publisher import SteamPublisher
from build_bridge.models import Project, PublishProfile, StoreEnum
from build_bridge.views.dialogs.publish_profile_dialog import PublishProfileDialog


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
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
        )
        main_layout.addWidget(self.refresh_button)
        # --- End Refresh Button ---

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVisible(False)
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self.scroll_content = QWidget()
        self.vbox = QVBoxLayout(self.scroll_content)
        self.vbox.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.vbox.setContentsMargins(0, 0, 0, 0)
        self.vbox.setSpacing(5)
        self.scroll_area.setWidget(self.scroll_content)

        self.empty_message_label = QLabel("No builds available.")
        self.empty_message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_message_label.setStyleSheet("font-style: italic; color: gray;")
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
            self.scroll_area.setVisible(False)
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
            print("  - Builds found. Showing scroll area, hiding empty message.")
            self.scroll_area.setVisible(True)
            self.empty_message_label.setVisible(False)
        else:
            print("  - No builds found. Hiding scroll area, showing empty message.")
            if is_valid_dir:
                self.empty_message_label.setText("No builds available in the monitored directory.")
            self.scroll_area.setVisible(False)
            self.empty_message_label.setVisible(True)

class PublishProfileEntry(QWidget):
    store_publishers = {StoreEnum.itch: ItchPublisher, StoreEnum.steam: SteamPublisher}

    def __init__(self, build_root, session):
        """Points to and manages a Publish Profile.
        It switches to the right profile when user selects a store in dropdown"""
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

        # Main horizontal layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)

        # --- Left Side: Build Label and Platform Selector ---
        project_name_str = "Unknown Project" 
        try:
            project = session.query(Project).one_or_none()
            if project:
                project_name_str = project.name
        except Exception as e:
            print(f"Error fetching project name: {e}")
        

        # Build Label
        self.label = QLabel(f"{project_name_str} - {self.build_id}")
        # Let the label take necessary space, MinimumExpanding allows growth if needed
        self.label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        self.label.setWordWrap(True)  # Allow wrapping if name is too long
        self.label.setMaximumWidth(350)

        # Platform Selector
        self.store_type_label = QLabel("Target Platform:")
        self.store_type_label.setStyleSheet("font-weight: bold;")
        self.store_type_combo = QComboBox()
        self.store_type_combo.setMinimumWidth(
            100
        )  # Give combo box a decent minimum size

        # Populate ComboBox
        for store_enum in self.store_publishers.keys():
            self.store_type_combo.addItem(str(store_enum.value), store_enum)

        # --- Right Side: Action Buttons ---
        browse_archive_button = QPushButton("Browse")
        browse_archive_button.setToolTip(f"Open build folder:\n{self.build_root}")
        browse_archive_button.setFixedHeight(28)  # Keep fixed height for consistency
        browse_archive_button.clicked.connect(self.browse_archive_directory)

        self.edit_button = QPushButton("Profile")
        self.edit_button.setToolTip(
            "Edit publish profile for the selected target platform"
        )
        self.edit_button.setFixedHeight(28)
        self.edit_button.clicked.connect(self.edit_publish_profile)

        self.publish_button = QPushButton("Publish")
        self.publish_button.setFixedHeight(28)
        self.publish_button.clicked.connect(self.handle_publish)
        self.publish_button.setToolTip("")  # Tooltip updated dynamically by can_publish

        # --- Assemble Layout ---
        layout.addWidget(self.label)
        layout.addWidget(self.store_type_label)
        layout.addWidget(self.store_type_combo)

        layout.addStretch(1)
        layout.addWidget(browse_archive_button)
        layout.addWidget(self.edit_button)
        layout.addWidget(self.publish_button)

        # Connect signals after widgets are created
        self.store_type_combo.currentIndexChanged.connect(self.on_store_changed)

        # Initial state check for publish button
        # Defer initial check slightly or ensure profile data is ready if needed immediately
        self.on_store_changed()  # Call to set initial state

        self.setLayout(layout)  # Set the layout for the widget

    def update_publish_button_enabled(self):
        self.publish_button.setEnabled(self.can_publish())

    def on_store_changed(self):
        # Called when the Store dropdown selection changes
        self.update_publish_profile()
        self.update_publish_button_enabled()

    def on_publish_profile_added_or_updated(self):
        # Called after the profile dialog is closed (if signal connected)
        self.publish_button.setEnabled(self.can_publish())

    def update_publish_profile(self):
        selected_store_enum = self.store_type_combo.currentData()

        if selected_store_enum is None:  # Should not happen
            return

        # Use main session to update profile
        existing_publish_profile = (
            self.session.query(PublishProfile)
            .filter_by(store_type=selected_store_enum.value, build_id=self.build_id)
            .first()
        )
        
        if existing_publish_profile:
            self.publish_profile = existing_publish_profile

        # CREATE NEW PUBLISH PROFILE
        if not existing_publish_profile:
            project = self.session.query(Project).one_or_none()
            # The profile does not exist for this store and this build. We create it
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
        """Checks if the current configuration allows publishing."""
        selected_platform_enum = self.store_type_combo.currentData()

        try:
            self.validate_build_content()

            # TODO: Using Publisher for validation here is bad. Validating data
            # should be done in a separate layer
            publisher_class = self.store_publishers.get(selected_platform_enum)
            if not publisher_class:
                raise InvalidConfigurationError(
                    f"No publisher implementation found for {selected_platform_enum.value}"
                )

            publisher_instance = publisher_class(
                publish_profile=self.publish_profile
            )  # Instantiate publisher

            publisher_instance.validate_publish_profile()

            # If all checks pass
            self.publish_button.setToolTip(
                f"Publish build '{self.build_id}' to {selected_platform_enum.value}"
            )
            return True

        except InvalidConfigurationError as e:
            # Update tooltip with the specific configuration error
            self.publish_button.setToolTip(f"Cannot publish: {e}")
            # Optionally log the error too
            # print(f"Validation Error for build '{self.build_id}', platform '{selected_platform_enum.value}': {e}")
            return False
        except Exception as e:  # Catch unexpected errors during validation
            self.publish_button.setToolTip(f"Unexpected validation error: {e}")
            print(f"Unexpected validation error: {e}")  # Log unexpected errors
            return False

    def validate_build_content(self):
        """Validates that the build directory looks like a build (e.g., contains .exe)."""
        # Renamed from 'validate' to be more specific

        if not self.build_root or not os.path.isdir(self.build_root):
            self.publish_button.setToolTip(
                f"Build directory is invalid or not found:\n{self.build_root}"
            )
            return False

        if not self.build_root or not os.path.isdir(self.build_root):
            raise InvalidConfigurationError("Build directory path is invalid.")

        # Check for .exe (Windows focus, adjust if needed for cross-platform)
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
                    break  # Found the first directory

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
            # dialog.profile_changed_signal.disconnect(self.on_publish_profile_added_or_updated) # If needed
            pass
        except TypeError:
            pass
        # Connect signal to re-check publish possibility after editing
        edit_dialog.profile_changed_signal.connect(self.on_publish_profile_added_or_updated)
        edit_dialog.exec()

    def handle_publish(self):
        selected_platform_enum = self.store_type_combo.currentData()
        if (
            selected_platform_enum is None
        ):  # Should not happen if button is enabled, but check anyway
            QMessageBox.warning(self, "Error", "No target platform selected.")
            return

        publisher_class = self.store_publishers.get(selected_platform_enum)
        if not publisher_class:
            QMessageBox.critical(
                self, "Error", f"No publisher found for {selected_platform_enum.value}"
            )
            return

        publisher_instance = publisher_class(self.publish_profile)

        print(
            f"Attempting to publish build '{self.build_id}' to {selected_platform_enum.value}..."
        )

        try:
            # The publisher's 'publish' method should internally fetch
            # the necessary profile using session_scope and validate again if needed.
            publisher_instance.publish(
                content_dir=self.build_root
            )
        except InvalidConfigurationError as e:
            # Technically this should never happen because publish button should be unclickable if validation fails.
            QMessageBox.warning(
                self,
                "Publishing Error",
                f"Failed to publish '{self.build_id}' to {selected_platform_enum.value}:\n\n{str(e)}",
            )
        except NotImplementedError:  # If a publisher's publish method isn't done
            QMessageBox.critical(
                self,
                "Not Implemented",
                f"Publishing for {selected_platform_enum.value} is not yet implemented.",
            )
        except Exception as e:  # Catch other potential errors during publish
            print(f"Error during publish execution: {e}")  # Log it
            QMessageBox.critical(
                self,
                "Publishing Failed",
                f"An unexpected error occurred while publishing to {selected_platform_enum.value}:\n\n{str(e)}",
            )

    def closeEvent(self, a0):
        self.session.close()
        return super().closeEvent(a0)
