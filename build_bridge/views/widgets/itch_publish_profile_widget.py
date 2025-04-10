from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QComboBox,
)

from PyQt6.QtCore import pyqtSignal

from build_bridge.models import BuildTarget, Project, ItchConfig, ItchPublishProfile, StoreEnum
from build_bridge.views.dialogs import settings_dialog


class ItchPublishProfileWidget(QWidget):
    profile_saved_signal = pyqtSignal()

    def __init__(self, session, build_id: str, parent=None):
        super().__init__(parent)
        self.session = session

        self.build_id = build_id  # The build_id of the profile to load/create

        # Attempt to load existing profile or prepare a new one
        self.profile = None
        self._load_or_initialize_profile()

        # Set window title based on whether it's new or existing
        if self.profile and self.session.is_modified(self.profile):
            self.setWindowTitle(f"Create Itch.io Publish Profile ({self.build_id})")
        elif self.profile:
            self.setWindowTitle(f"Edit Itch.io Publish Profile ({self.build_id})")
        else:
            # Should not happen if _load_or_initialize_profile works correctly
            self.setWindowTitle("Itch.io Publish Profile Error")
            QMessageBox.critical(self, "Error", "Failed to load or initialize profile.")
            return  # Prevent further initialization if profile loading failed

        self._init_ui()
        self._populate_fields()  # Populate UI fields after UI is built

    def _load_or_initialize_profile(self):
        """Loads the profile by build_id or prepares data for a new instance."""
        self.is_new_profile = False  # Reset flag
        try:
            self.profile = (
                self.session.query(ItchPublishProfile)
                .filter_by(build_id=self.build_id)
                .one_or_none()
            )

            if self.profile is None:
                print(
                    f"Preparing new Itch.io Publish Profile for build {self.build_id}"
                )
                # Create a transient instance, DO NOT add to session yet
                self.profile = ItchPublishProfile(build_id=self.build_id, store_type=StoreEnum.itch)
                self.is_new_profile = True
                # Set defaults for transient object display
                self.profile.itch_user_game_id = ""
                self.profile.itch_channel_name = "default-channel"

        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to load profile: {e}")
            self.profile = None  # Ensure profile is None if loading failed

    def _init_ui(self):
        """Initialize the User Interface elements."""
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # --- Project Selection ---
        self.project_combo = QComboBox()
        self.project_combo.currentIndexChanged.connect(self._on_project_changed)
        form_layout.addRow("Project:", self.project_combo)

        # --- Read-only Build ID ---
        self.build_id_input = QLineEdit(self.build_id)
        self.build_id_input.setReadOnly(True)
        form_layout.addRow("Build ID:", self.build_id_input)

        # --- Itch.io User/Game ID ---
        self.user_game_id_input = QLineEdit()
        self.user_game_id_input.setPlaceholderText("username/game-slug")
        self.user_game_id_input.setToolTip("Format: username/game-slug")
        form_layout.addRow("User/Game ID:", self.user_game_id_input)

        # --- Itch.io Channel Name ---
        self.channel_name_input = QLineEdit()
        self.channel_name_input.setPlaceholderText("default-channel")
        self.channel_name_input.setToolTip(
            "The channel name for publishing (e.g., windows-beta)"
        )
        form_layout.addRow("Channel Name:", self.channel_name_input)

        # --- Itch.io Authentication ---
        auth_layout = QHBoxLayout()
        self.auth_combo = QComboBox()
        self.auth_combo.setToolTip("Select the Itch.io account to use for publishing.")
        self.itch_config_button = QPushButton("Manage Itch.io Configuration")
        self.itch_config_button.clicked.connect(self._open_itch_settings)
        auth_layout.addWidget(self.auth_combo)
        form_layout.addRow("Itch.io Auth:", auth_layout)

        main_layout.addLayout(form_layout)
        main_layout.addWidget(self.itch_config_button)

        # --- Save Button ---
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_profile)

        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def _populate_fields(self):
        """Populate UI fields with data from self.profile."""
        if not self.profile:
            # This case should ideally be handled before UI init, but as a safeguard:
            QMessageBox.critical(self, "Error", "Profile data is not available.")
            return

        # Load Projects into ComboBox
        self._load_projects()

        # Load Auth options into ComboBox
        self._refresh_auth_options()  # Also handles selecting current auth

        # --- Populate based on loaded/new profile ---
        if self.profile.id is not None:  # Check if it's an existing profile (has an ID)
            # Select current project
            if self.profile.project:
                project_index = self.project_combo.findData(
                    self.profile.project.id
                )  # Find by ID
                if project_index >= 0:
                    self.project_combo.setCurrentIndex(project_index)
                else:
                    # Handle case where saved project is no longer valid
                    QMessageBox.warning(
                        self,
                        "Warning",
                        f"Saved project '{self.profile.project.name}' not found. Please select a project.",
                    )

            # Set other fields
            bt = self.session.query(BuildTarget).one_or_none()
            if bt:
                platform = bt.target_platform.lower()

            if preset_channel := self.profile.itch_channel_name:
                channel_name = preset_channel
            elif bt:
                channel_name = platform
            else:
                channel_name = ""

            print(f"ItchPublishProfile: setting channel_name to {channel_name}")
            self.user_game_id_input.setText(self.profile.itch_user_game_id or "")
            self.channel_name_input.setText(channel_name)

        else:
            # Defaults for a new profile
            self.user_game_id_input.setText("")
            self.channel_name_input.setText("default-channel")

        # Trigger initial display update for builder path (important for new profiles too)
        self._on_project_changed()

    def _load_projects(self):
        """Load all projects into the project dropdown."""
        self.project_combo.clear()
        try:
            projects = self.session.query(Project).order_by(Project.name).all()
            if not projects:
                self.project_combo.addItem("No projects found", None)
                self.project_combo.setEnabled(False)
                QMessageBox.warning(
                    self,
                    "No Projects",
                    "No projects found in the database. Please add projects first.",
                )
            else:
                self.project_combo.addItem(
                    "Select a Project...", None
                )  # Placeholder item
                for project in projects:
                    # Store project ID as data for reliable retrieval
                    self.project_combo.addItem(project.name, project.id)
                self.project_combo.setCurrentIndex(1)
        except Exception as e:
            QMessageBox.critical(
                self, "Database Error", f"Failed to load projects: {e}"
            )
            self.project_combo.setEnabled(False)

    def _on_project_changed(self):
        """Update the read-only builder path based on selected project and update profile project."""
        path = "N/A - Select a project"
        if self.profile.project is None and self.project_combo.currentData():
            # If selected project is valid and exists, then assign it to the profile
            project = self.session.query(Project).get(self.project_combo.currentData())
            if project:
                self.profile.project = project

    def _open_itch_settings(self):
        settings = settings_dialog.SettingsDialog(
            default_page=2
        )  # Assuming Itch.io settings is page 3
        settings.exec()
        self._refresh_auth_options()

    def _refresh_auth_options(self):
        """Refresh the Itch.io Auth dropdown and try to re-select current."""
        user_selected_auth = self.auth_combo.currentData()
        self.auth_combo.clear()
        try:
            itch_config = (
                self.session.query(ItchConfig).order_by(ItchConfig.username).all()
            )

            if self.profile and self.profile.itch_config:
                current_auth_id = self.profile.itch_config.id
            elif itch_config:
                current_auth_id = itch_config[0].id
            else:
                selected_index = -1  # Default to no selection

            if not itch_config:
                self.auth_combo.addItem("No Itch.io accounts configured", None)
                self.auth_combo.setEnabled(False)
            else:
                self.auth_combo.setEnabled(True)
                self.auth_combo.addItem("Select Auth Profile...", None)  # Placeholder
                for i, auth in enumerate(itch_config):
                    # Store auth ID as data for reliable retrieval
                    if auth.username:
                        self.auth_combo.addItem(auth.username, auth.id)
                    if auth.id == current_auth_id or auth.id == user_selected_auth:
                        selected_index = i + 1  # +1 because of placeholder item

                if selected_index != -1:
                    self.auth_combo.setCurrentIndex(selected_index)
                elif current_auth_id is not None:
                    # Saved auth ID exists but wasn't found in the current list
                    QMessageBox.warning(
                        self,
                        "Auth Not Found",
                        f"Previously selected Itch.io account ID {current_auth_id} not found. Please re-select.",
                    )

        except Exception as e:
            QMessageBox.critical(
                self, "Database Error", f"Failed to load Itch.io authentications: {e}"
            )
            self.auth_combo.setEnabled(False)

    def save_profile(self):
        """Validate inputs and save the current profile's details."""
        if not self.profile:
            QMessageBox.critical(self, "Error", "Cannot save, profile data is missing.")
            return

        # --- Input Validation ---
        selected_project_id = self.project_combo.currentData()
        if selected_project_id is None:
            QMessageBox.warning(self, "Validation Error", "Please select a Project.")
            self.project_combo.setFocus()
            return

        user_game_id = self.user_game_id_input.text().strip()
        if not user_game_id or "/" not in user_game_id:
            QMessageBox.warning(
                self,
                "Validation Error",
                "Please enter a valid User/Game ID (format: username/game-slug).",
            )
            self.user_game_id_input.setFocus()
            return

        channel_name = self.channel_name_input.text().strip()
        if not channel_name:
            QMessageBox.warning(
                self, "Validation Error", "Please enter a Channel Name."
            )
            self.channel_name_input.setFocus()
            return

        selected_auth_id = self.auth_combo.currentData()
        if selected_auth_id is None:
            QMessageBox.warning(
                self,
                "Validation Error",
                "Please select an Itch.io Authentication account.",
            )
            self.auth_combo.setFocus()
            return

        # --- Update Profile Object ---
        try:
            # Fetch related objects from DB using validated IDs
            selected_project = (
                self.session.query(Project).filter_by(id=selected_project_id).one()
            )
            selected_auth = (
                self.session.query(ItchConfig).filter_by(id=selected_auth_id).one()
            )

            # !!! Add the profile to the session ONLY if it's new !!!
            if self.is_new_profile:
                # Now it's safe to add, as we're about to set required fields
                self.session.add(self.profile)

            # Assign validated values (including the required project)
            self.profile.project = selected_project
            self.profile.itch_user_game_id = user_game_id
            self.profile.itch_channel_name = channel_name
            self.profile.itch_config = selected_auth

            # --- Commit Changes ---
            self.session.commit()
            self.profile_saved_signal.emit()

            QMessageBox.information(self, "Success", "Profile saved successfully.")

        except Exception as e:
            self.session.rollback()  # Rollback on any error during commit
            QMessageBox.critical(
                self, "Save Error", f"An error occurred while saving:\n{e}"
            )
