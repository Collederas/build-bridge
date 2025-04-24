from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QFileDialog,
    QComboBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QHeaderView,
)

from PyQt6.QtCore import pyqtSignal
from sqlalchemy.orm import object_session

from build_bridge.models import (
    Project,
    PublishProfile,
    SteamConfig,
    SteamPublishProfile,
    StoreEnum,
)
from build_bridge.views.dialogs import settings_dialog


class SteamPublishProfileWidget(QWidget):
    profile_saved_signal = pyqtSignal()

    def __init__(self, publish_profile: SteamPublishProfile, session, parent=None):
        super().__init__(parent)
        self.publish_profile = publish_profile
        self.session = session

        self._init_ui()
        self._populate_fields()

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

        # --- App ID ---
        self.app_id_input = QSpinBox()
        self.app_id_input.setRange(0, 9999999)  # Set a reasonable range for App IDs
        self.app_id_input.setToolTip("The Steam App ID for your game.")
        form_layout.addRow("App ID:", self.app_id_input)

        # --- Description ---
        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText(
            "Optional: Live branch name, build notes, etc."
        )
        form_layout.addRow("Description:", self.description_input)

        # --- Builder Path (Read-Only Display) ---
        self.builder_path_display = QLineEdit()
        self.builder_path_display.setReadOnly(True)
        self.builder_path_display.setToolTip(
            "Managed by Build Bridge. This is where Steam config files and upload logs will go."
        )
        form_layout.addRow("Builder Path:", self.builder_path_display)

        # --- Depots Table ---
        self.depots_table = QTableWidget(0, 3)
        self.depots_table.setHorizontalHeaderLabels(
            ["Depot ID", "Path (Directory)", "Browse"]
        )
        self.depots_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.depots_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        # Adjust column widths (optional)
        self.depots_table.horizontalHeader().setStretchLastSection(False)
        self.depots_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.depots_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.depots_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )

        form_layout.addRow("Depots:", self.depots_table)

        # --- Depot Add/Remove Buttons ---
        depot_button_layout = QHBoxLayout()
        self.add_depot_button = QPushButton("Add Depot")
        self.add_depot_button.clicked.connect(self._add_depot_row)
        self.remove_depot_button = QPushButton("Remove Selected Depot")
        self.remove_depot_button.clicked.connect(self._remove_depot_row)
        depot_button_layout.addWidget(self.add_depot_button)
        depot_button_layout.addWidget(self.remove_depot_button)
        depot_button_layout.addStretch()
        form_layout.addRow(depot_button_layout)  # Add below the table

        # --- Steam Authentication ---
        auth_layout = QHBoxLayout()
        self.auth_combo = QComboBox()
        self.auth_combo.setToolTip("Select the Steam account to use for publishing.")
        self.steam_config_button = QPushButton("Manage Steam Configuration")
        self.steam_config_button.clicked.connect(self._open_steam_settings)
        auth_layout.addWidget(self.auth_combo)
        form_layout.addRow("Steam Auth:", auth_layout)

        main_layout.addLayout(form_layout)
        main_layout.addWidget(self.steam_config_button)

        self.setLayout(main_layout)

    def _populate_fields(self):
        """Populate UI fields with data from self.publish_profile."""

        # Load Projects into ComboBox
        with self.session.no_autoflush:
            self._load_projects()
            self._refresh_auth_options()

            # --- Populate based on loaded/new profile ---

            # Select current project
            if self.publish_profile.project:
                project_index = self.project_combo.findData(
                    self.publish_profile.project.id
                )  # Find by ID
                if project_index >= 0:
                    self.project_combo.setCurrentIndex(project_index)
                else:
                    # Handle case where saved project is no longer valid?
                    QMessageBox.warning(
                        self,
                        "Warning",
                        f"Saved project '{self.publish_profile.project.name}' not found. Please select a project.",
                    )

                # Is there another publish profile for steam on this project? Then let's use it
                # as most likely thing didn't change that much
                existing_profile = self.session.query(PublishProfile).filter_by(
                    project=self.publish_profile.project, store_type=StoreEnum.steam
                ).order_by(PublishProfile.build_id.desc()).first()

                app_id = (
                    self.publish_profile.app_id
                    or (existing_profile and existing_profile.app_id)
                    or 480
                )

                description = (
                    self.publish_profile.description
                    or (existing_profile and existing_profile.description)
                    or ""
                )

                depots = (
                    self.publish_profile.depots
                    or (existing_profile and existing_profile.depots)
                    or {}
                )

                # Set other fields
                self.app_id_input.setValue(app_id)
                self.description_input.setText(description)
                self._load_depots_table(depots)

            else:
                # Defaults for a new profile
                self.app_id_input.setValue(480)
                self.description_input.setText("")
                self._load_depots_table({})  # Empty table

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

    def _refresh_auth_options(self):
        """Refresh the Steam Auth dropdown and try to re-select current SteamConfig.
        This is a bit pointless now because in settings -for now- only
        1 config can be added.
        """
        self.auth_combo.clear()
        steam_config = self.session.query(SteamConfig).first()

        try:
            if not steam_config:
                self.auth_combo.setEnabled(False)
            else:
                self.auth_combo.setEnabled(True)
                self.auth_combo.addItem(steam_config.username, steam_config.id)
            
            self.auth_combo.setCurrentIndex(0)

        except Exception as e:
            QMessageBox.critical(
                self, "Database Error", f"Failed to load Steam Config: {e}"
            )
            self.auth_combo.setEnabled(False)

    def _on_project_changed(self):
        """Update the read-only builder path based on selected project and update profile project."""
        path = "N/A - Select a project"
        if self.publish_profile.project is None and self.project_combo.currentData():
            # If selected project is valid and exists, then assign it to the profile
            project = self.session.query(Project).get(self.project_combo.currentData())
            if project:
                self.publish_profile.project = project

        if self.publish_profile.project is not None:
            try:
                path = self.publish_profile.builder_path
            except NoResultFound:
                path = "N/A - Project not found"
            except Exception as e:
                path = f"Error loading path: {e}"

        self.builder_path_display.setText(path)

    def _load_depots_table(self, depots_dict: dict):
        """Load depots into the table."""
        self.depots_table.setRowCount(0)  # Clear existing rows
        if not isinstance(depots_dict, dict):
            print(f"Warning: Depots data is not a dictionary: {depots_dict}")
            return  # Or show a warning messagebox

        for depot_id, depot_path in depots_dict.items():
            self._insert_depot_row(depot_id, depot_path)

    def _insert_depot_row(self, depot_id=None, depot_path=None):
        """Inserts a row into the depot table and sets up widgets."""
        row = self.depots_table.rowCount()
        self.depots_table.insertRow(row)

        # Depot ID Item (Make it editable)
        id_item = QTableWidgetItem(str(depot_id) if depot_id is not None else "")
        self.depots_table.setItem(row, 0, id_item)

        # Path Item (Make it editable, though Browse is preferred)
        path_item = QTableWidgetItem(depot_path or "")
        self.depots_table.setItem(row, 1, path_item)

        # Browse Button
        browse_button = QPushButton("Browse...")
        # Use lambda with default argument to capture current row correctly
        browse_button.clicked.connect(
            lambda checked=False, r=row: self._browse_depot_path(r)
        )
        self.depots_table.setCellWidget(row, 2, browse_button)

    def _add_depot_row(self):
        """Adds a new, empty row to the depots table."""
        self._insert_depot_row()
        # Optionally, scroll to the new row and start editing the ID
        self.depots_table.scrollToBottom()
        # self.depots_table.editItem(self.depots_table.item(self.depots_table.rowCount() - 1, 0))

    def _remove_depot_row(self):
        """Removes the currently selected row from the depots table."""
        current_row = self.depots_table.currentRow()
        if current_row >= 0:
            self.depots_table.removeRow(current_row)
        else:
            QMessageBox.warning(
                self, "No Selection", "Please select a depot row to remove."
            )

    def _browse_depot_path(self, row):
        """Open a directory dialog to select a depot path."""
        current_path_item = self.depots_table.item(row, 1)
        start_dir = (
            current_path_item.text()
            if current_path_item and current_path_item.text()
            else str(self.publish_profile.project.builds_path)
        )  # Start Browse from current path if set

        path = QFileDialog.getExistingDirectory(
            self, "Select Depot Directory", start_dir
        )
        if path:
            # Update the corresponding item in the table
            self.depots_table.setItem(row, 1, QTableWidgetItem(path))

    def _open_steam_settings(self):
        settings = settings_dialog.SettingsDialog(default_page=1)
        settings.exec()
        self._refresh_auth_options()

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

        app_id = self.app_id_input.value()
        if app_id <= 0:
            QMessageBox.warning(
                self, "Validation Error", "Please enter a valid App ID (must be > 0)."
            )
            self.app_id_input.setFocus()
            return

        selected_auth_id = self.auth_combo.currentData()
        if selected_auth_id is None:
            QMessageBox.warning(
                self,
                "Validation Error",
                "Please select a Steam Authentication account.",
            )
            self.auth_combo.setFocus()
            return

        # --- Depot Validation and Collection ---
        depots_to_save = {}
        for row in range(self.depots_table.rowCount()):
            id_item = self.depots_table.item(row, 0)
            path_item = self.depots_table.item(row, 1)

            if not id_item or not id_item.text().strip():
                QMessageBox.warning(
                    self, "Validation Error", f"Depot ID is missing in row {row+1}."
                )
                self.depots_table.selectRow(row)
                self.depots_table.setFocus()
                return
            if not path_item or not path_item.text().strip():
                QMessageBox.warning(
                    self, "Validation Error", f"Depot Path is missing in row {row+1}."
                )
                self.depots_table.selectRow(row)
                self.depots_table.setFocus()
                return

            try:
                depot_id = int(id_item.text().strip())
                if depot_id <= 0:
                    raise ValueError("Depot ID must be positive")
            except ValueError:
                QMessageBox.warning(
                    self,
                    "Validation Error",
                    f"Invalid Depot ID '{id_item.text()}' in row {row+1}. Must be a positive integer.",
                )
                self.depots_table.selectRow(row)
                self.depots_table.editItem(id_item)  # Focus the problematic cell
                return

            depot_path = path_item.text().strip()
            # Add more checks? e.g., os.path.isdir(depot_path)

            if depot_id in depots_to_save:
                QMessageBox.warning(
                    self,
                    "Validation Error",
                    f"Duplicate Depot ID '{depot_id}' found in row {row+1}.",
                )
                self.depots_table.selectRow(row)
                self.depots_table.editItem(id_item)
                return

            depots_to_save[depot_id] = depot_path

        # --- Update Profile Object ---
        try:
            if not object_session(self.publish_profile):
                self.session.add(self.publish_profile)

            # Assign validated values (including the required project)
            self.publish_profile.project_id = selected_project_id
            self.publish_profile.app_id = app_id
            self.publish_profile.description = self.description_input.text().strip()

            # Builder path is derived, not saved explicitly
            self.publish_profile.steam_config_id = selected_auth_id
            self.publish_profile.depots = (
                depots_to_save  # Assign the validated dictionary
            )

            # --- Commit Changes ---
            self.session.commit()
            self.profile_saved_signal.emit()
            QMessageBox.information(
                self,
                "Success",
                f"Steam Profile for build {self.publish_profile.build_id} saved successfully.",
            )

        except Exception as e:
            self.session.rollback()  # Rollback on any error during commit
            QMessageBox.critical(
                self, "Save Error", f"An error occurred while saving:\n{e}"
            )
