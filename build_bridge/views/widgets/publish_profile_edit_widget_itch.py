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
from sqlalchemy.orm import object_session

from build_bridge.database import session_scope
from build_bridge.models import BuildTarget, Project, ItchConfig, ItchPublishProfile
from build_bridge.views.dialogs import settings_dialog


class ItchPublishProfileWidget(QWidget):
    profile_saved_signal = pyqtSignal()

    def __init__(self, publish_profile: ItchPublishProfile, session, parent=None):
        self.publish_profile = publish_profile
        self.session = session # used to commit the session and query auxiliary models

        super().__init__(parent=parent) 
        self.setWindowTitle(f"Edit Itch.io Publish Profile ({publish_profile.build_id})")

        self._init_ui()
        self._populate_fields()  # Populate UI fields after UI is built

    def _init_ui(self):
        """Initialize the User Interface elements."""
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # --- Project Selection ---
        self.project_combo = QComboBox()
        self.project_combo.currentIndexChanged.connect(self._on_project_changed)
        form_layout.addRow("Project:", self.project_combo)

        # --- Read-only Build ID ---
        self.build_id_input = QLineEdit(self.publish_profile.build_id)
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

        self.setLayout(main_layout)

    def _populate_fields(self):
        """Populate UI fields with data from self.profile."""

        with self.session.no_autoflush: # no autoflush because we might be editing a profile that is not saved yet.
            if not self.publish_profile:
                # This case should ideally be handled before UI init, but as a safeguard:
                QMessageBox.critical(self, "Error", "Profile data is not available.")
                return

            # Load Projects into ComboBox
            self._load_projects()

            # Load Auth options into ComboBox
            self._refresh_auth_options()

            # --- Populate based on loaded/new profile ---
            if self.publish_profile.id is not None:  # Check if it's an existing profile (has an ID)
                # Select current project
                if self.publish_profile.project:
                    project_index = self.project_combo.findData(
                        self.publish_profile.project.id
                    )  # Find by ID
                    if project_index >= 0:
                        self.project_combo.setCurrentIndex(project_index)
                    else:
                        # Handle case where saved project is no longer valid
                        QMessageBox.warning(
                            self,
                            "Warning",
                            f"Saved project '{self.publish_profile.project.name}' not found. Please select a project.",
                        )
            
            existing_channel = self.publish_profile.itch_channel_name
            
            # Check we dont have an existing channel
            if existing_channel and not existing_channel == "":
                print(f"ItchPublishProfileWidget: Setting initial channel name to existing value: {existing_channel}")
                channel_name = existing_channel
            else:
                bt = self.session.query(BuildTarget).one_or_none() # ASSUMED ONE FOR WHOLE APP

                if bt:
                    target_platform_lowercase = bt.target_platform.lower()
                print(f"ItchPublishProfileWidget: Setting initial channel name to inferred from platform of build target: {target_platform_lowercase}")
                channel_name = target_platform_lowercase

            self.channel_name_input.setText(channel_name)

            existing_game_id = self.publish_profile.itch_user_game_id
            game_id = ""

            if existing_game_id and not existing_game_id == "":
                game_id = existing_game_id
            else:
                # Do we have itch configured AND a project?
                conf = self.session.query(ItchConfig).one_or_none()
                proj = self.session.query(Project).one_or_none()

                if conf and proj:
                    # Then we can make a guess
                    game_id = f"{conf.username}/{proj.name.lower().replace(' ', '-')}"
            
            self.user_game_id_input.setText(game_id)
    

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
        # If project changes, we update the publish profile
        if current_proj := self.project_combo.currentData():  # data = proj_id
            project = self.session.query(Project).get(current_proj)
            self.publish_profile.project = project

    def _open_itch_settings(self):
        settings = settings_dialog.SettingsDialog(
            default_page=2
        )  # Assuming Itch.io settings is page 3
        settings.exec()

        # Refresh settings when back
        self._refresh_auth_options()

    def _refresh_auth_options(self):
        """Refresh the Itch.io Auth dropdown. This is to detect if there is a configured ItchConfig in the db."""
        self.auth_combo.clear()

        with session_scope() as session:
            itch_config = session.query(ItchConfig).one_or_none()

            try:
                if not itch_config:
                    self.auth_combo.addItem("No Itch.io accounts configured", None)
                    self.auth_combo.setEnabled(False)
                else:
                    self.auth_combo.setEnabled(True)
                    self.auth_combo.addItem("Select Auth Profile...", None)
                    self.auth_combo.addItem(itch_config.username, itch_config.id)

                self.auth_combo.setCurrentIndex(1)

            except Exception as e:
                QMessageBox.critical(
                    self, "Database Error", f"Failed to load Itch.io authentications: {e}"
                )
                self.auth_combo.setEnabled(False)

    def save_profile(self):
        """Validate inputs and save the current profile's details."""
        if not self.publish_profile:
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

        try:

            # Add profile to session if it don't exist (it was created by the outer widget (PublishProfileEntry))
            if not object_session(self.publish_profile):
                self.session.add(self.publish_profile)

            # Assign validated values (including the required project)
            self.publish_profile.project_id = selected_project_id
            self.publish_profile.itch_user_game_id = user_game_id
            self.publish_profile.itch_channel_name = channel_name
            self.publish_profile.itch_config_id = selected_auth_id

            # --- Commit Changes ---
            self.session.commit()
            self.profile_saved_signal.emit()

            QMessageBox.information(self, "Success", "Profile saved successfully.")

        except Exception as e:
            self.session.rollback()  # Rollback on any error during commit
            QMessageBox.critical(
                self, "Save Error", f"An error occurred while saving:\n{e}"
            )
