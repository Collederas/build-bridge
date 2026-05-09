import copy
import logging
import os
from pathlib import Path, PosixPath, WindowsPath
from turtle import pd

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

from build_bridge.models import Project, SteamConfig, SteamPublishProfile
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
        """Initialize the User Interface elements with Tabs."""
        main_layout = QVBoxLayout(self)
        common_form_layout = QFormLayout()  # Layout for fields outside tabs

        # --- Common Fields (Outside Tabs) ---
        self.project_combo = QComboBox()
        self.project_combo.currentIndexChanged.connect(self._on_project_changed)
        common_form_layout.addRow("Project:", self.project_combo)

        self.build_id_input = QLineEdit(self.publish_profile.build_id)
        self.build_id_input.setReadOnly(True)
        common_form_layout.addRow("Build ID:", self.build_id_input)

        self.builder_path_display = QLineEdit()
        self.builder_path_display.setReadOnly(True)
        self.builder_path_display.setToolTip(
            "Managed by Build Bridge. This is where Steam config files and upload logs will go."
        )
        common_form_layout.addRow("Builder Path:", self.builder_path_display)

        main_layout.addLayout(common_form_layout)  # Add common fields first

        self.app_id_input = QSpinBox()
        self.app_id_input.setRange(0, 9999999)
        self.app_id_input.setToolTip("The Steam App ID for your main game.")
        common_form_layout.addRow("App ID:", self.app_id_input)

        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText(
            "Main, Demo, QA, ..."
        )
        common_form_layout.addRow("Profile Name:", self.description_input)

        self.depots_table = self._create_depots_table()
        main_layout.addWidget(self.depots_table)
        main_layout.addLayout(self._create_depot_buttons(self.depots_table))

        # Common Fields (Bottom)
        auth_layout = QHBoxLayout()
        self.auth_combo = QComboBox()
        self.auth_combo.setToolTip("Select the Steam account to use for publishing.")
        auth_layout.addWidget(self.auth_combo)
        # Add steam config button next to combo, or below separately
        common_form_layout.addRow("Steam Auth:", auth_layout)

        self.steam_config_button = QPushButton("Manage Steam Configuration")
        self.steam_config_button.clicked.connect(self._open_steam_settings)
        main_layout.addWidget(self.steam_config_button)

        self.setLayout(main_layout)

    def _populate_fields(self):
        """Populate UI fields with data from self.publish_profile."""
        with self.session.no_autoflush:
            self._load_projects()
            self._refresh_auth_options()

            # Populate common fields
            if self.publish_profile.project:
                project_index = self.project_combo.findData(
                    self.publish_profile.project.id
                )
                if project_index >= 0:
                    self.project_combo.setCurrentIndex(project_index)
                else:
                    QMessageBox.warning(
                        self,
                        "Warning",
                        f"Saved project '{self.publish_profile.project.name}' not found.",
                    )
                # Trigger builder path update
                self._on_project_changed()  # Ensure builder path is updated early
            else:
                if (
                    self.project_combo.count() > 1
                ):  # Check if there are projects loaded besides placeholder
                    self.project_combo.setCurrentIndex(
                        1
                    )  # Select first actual project if profile has none
                else:
                    self.project_combo.setCurrentIndex(
                        0
                    )  # Select placeholder if no projects
                self._on_project_changed()  # Update builder path even if no project is selected initially

            # REGULAR TAB
            # Only use current profile values to avoid cross-profile data bleed.
            app_id = self.publish_profile.app_id or 480  # Default to Spacewar
            self.app_id_input.setValue(app_id)

            profile_name = (
                self.publish_profile.description
                or "Main"
            )
            self.description_input.setText(profile_name)

            # Regular Depots
            depots = copy.deepcopy(self.publish_profile.depots or {})
            if depots and self.publish_profile.project:
                depot_id = next(iter(depots))
                depots[depot_id] = (
                    f"{self.publish_profile.project.builds_path}/"
                    f"{self.build_id_input.text()}"
                ).replace(os.sep, "/")

            self._load_depots_table(self.depots_table, depots)

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
        """Refresh the Steam Auth dropdown and re-select current SteamConfig when possible."""
        self.auth_combo.clear()
        current_steam_config_id = getattr(self.publish_profile, "steam_config_id", None)
        steam_configs = (
            self.session.query(SteamConfig).order_by(SteamConfig.username.asc()).all()
        )

        try:
            if not steam_configs:
                self.auth_combo.setEnabled(False)
            else:
                self.auth_combo.setEnabled(True)
                self.auth_combo.addItem("Select Auth Profile...", None)
                for steam_config in steam_configs:
                    self.auth_combo.addItem(steam_config.username, steam_config.id)

            if current_steam_config_id is not None:
                selected_index = self.auth_combo.findData(current_steam_config_id)
                self.auth_combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
            else:
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

    def _create_depots_table(self):
        """Helper function to create a depots table widget."""
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Depot ID", "Path (Directory)", "Browse"])
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        return table

    def _create_depot_buttons(self, target_table):
        """Helper function to create Add/Remove buttons for a specific depot table."""
        layout = QHBoxLayout()
        add_button = QPushButton("Add Depot")
        # Pass the target table to the slot
        add_button.clicked.connect(lambda: self._add_depot_row(target_table))
        remove_button = QPushButton("Remove Selected Depot")
        # Pass the target table to the slot
        remove_button.clicked.connect(lambda: self._remove_depot_row())
        layout.addWidget(add_button)
        layout.addWidget(remove_button)
        layout.addStretch()
        return layout

    def _load_depots_table(self, table_widget: QTableWidget, depots_dict: dict):
        """Load depots into the specified table."""
        table_widget.setRowCount(0)  # Clear existing rows
        if not isinstance(depots_dict, dict):
            logging.info(f"Warning: Depots data is not a dictionary: {depots_dict}")
            return
        for depot_id, depot_path in depots_dict.items():
            # Pass the target table to _insert_depot_row
            self._insert_depot_row(table_widget, depot_id, depot_path)

    def _insert_depot_row(
        self, table_widget: QTableWidget, depot_id=None, depot_path=None
    ):
        """Inserts a row into the specified depot table and sets up widgets."""
        row = table_widget.rowCount()
        table_widget.insertRow(row)

        id_item = QTableWidgetItem(str(depot_id) if depot_id is not None else "")
        table_widget.setItem(row, 0, id_item)

        path_item = QTableWidgetItem(depot_path or "")
        table_widget.setItem(row, 1, path_item)

        browse_button = QPushButton("Browse...")

        browse_button.clicked.connect(
            lambda checked=False, tbl=table_widget, r=row: self._browse_depot_path(
                tbl, r
            )
        )
        table_widget.setCellWidget(row, 2, browse_button)

    def _add_depot_row(self, table_widget: QTableWidget):
        """Adds a new, empty row to the specified depots table."""
        self._insert_depot_row(table_widget)
        table_widget.scrollToBottom()

    def _remove_depot_row(self):
        """Removes the currently selected row from the depots table."""
        current_row = self.depots_table.currentRow()
        if current_row >= 0:
            self.depots_table.removeRow(current_row)
        else:
            QMessageBox.warning(
                self, "No Selection", "Please select a depot row to remove."
            )

    def _browse_depot_path(self, table_widget: QTableWidget, row):
        """Open a directory dialog to select a depot path for the specified table."""
        current_path_item = table_widget.item(row, 1)
        start_dir = ""
        if current_path_item and current_path_item.text():
            start_dir = current_path_item.text()
        elif self.publish_profile.project and self.publish_profile.project.builds_path:
            # Default to project's build path if available
            start_dir = str(self.publish_profile.project.builds_path)

        path = QFileDialog.getExistingDirectory(
            self, "Select Depot Directory", start_dir
        )
        if path:
            table_widget.setItem(row, 1, QTableWidgetItem(path))

    def _open_steam_settings(self):
        settings = settings_dialog.SettingsDialog(default_page=1)
        settings.exec()
        self._refresh_auth_options()

    def _collect_and_validate_depots(self, table_widget: QTableWidget):
        """Helper to collect and validate depots from a specific table.
        Returns a dictionary of depots or None if validation fails.
        """
        depots_to_save = {}
        for row in range(table_widget.rowCount()):
            id_item = table_widget.item(row, 0)
            path_item = table_widget.item(row, 1)

            if not id_item or not id_item.text().strip():
                QMessageBox.warning(
                    self, "Validation Error", f"Depot ID is missing in row {row+1}."
                )
                table_widget.selectRow(row)
                table_widget.setFocus()
                return None
            if not path_item or not path_item.text().strip():
                QMessageBox.warning(
                    self, "Validation Error", f"Depot Path is missing in row {row+1}."
                )
                table_widget.selectRow(row)
                table_widget.setFocus()
                return None

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
                table_widget.selectRow(row)
                table_widget.editItem(id_item)
                return None

            depot_path = path_item.text().strip()

            if depot_id in depots_to_save:
                QMessageBox.warning(
                    self,
                    "Validation Error",
                    f"Duplicate Depot ID '{depot_id}' found in row {row+1}.",
                )
                table_widget.selectRow(row)
                table_widget.editItem(id_item)
                return None

            depots_to_save[depot_id] = depot_path
        return depots_to_save

    def save_profile(self):
        """Validate inputs and save the current profile's details for both tabs."""
        if not self.publish_profile:
            QMessageBox.critical(self, "Error", "Cannot save, profile data is missing.")
            return False

        # Common Input Validation
        selected_project_id = self.project_combo.currentData()
        if selected_project_id is None:
            QMessageBox.warning(self, "Validation Error", "Please select a Project.")
            self.project_combo.setFocus()
            return False

        selected_auth_id = self.auth_combo.currentData()
        if selected_auth_id is None:
            QMessageBox.warning(
                self,
                "Validation Error",
                "Please select a Steam Authentication account.",
            )
            self.auth_combo.setFocus()
            return False

        profile_name = self.description_input.text().strip()
        if not profile_name:
            QMessageBox.warning(
                self,
                "Validation Error",
                "Please enter a Profile Name.",
            )
            self.description_input.setFocus()
            return False

        # Regular Tab Validation
        app_id = self.app_id_input.value()
        if app_id <= 0:
            QMessageBox.warning(
                self,
                "Validation Error",
                "Please enter a valid App ID (must be > 0).",
            )
            self.app_id_input.setFocus()
            return False

        regular_depots = self._collect_and_validate_depots(self.depots_table)
        if regular_depots is None:
            return False

        # Update Profile Object
        try:
            if not object_session(self.publish_profile):
                self.session.add(self.publish_profile)

            # Assign common validated values
            self.publish_profile.project_id = selected_project_id
            self.publish_profile.steam_config_id = selected_auth_id

            # Assign Regular Tab values
            self.publish_profile.app_id = app_id
            self.publish_profile.description = profile_name
            self.publish_profile.depots = regular_depots

            # Commit Changes
            self.session.commit()
            self.profile_saved_signal.emit()
            QMessageBox.information(
                self,
                "Success",
                f"Steam Profile for build {self.publish_profile.build_id} saved successfully.",
            )
            return True

        except AttributeError as e:
            self.session.rollback()
            QMessageBox.critical(
                self,
                "Save Error",
                f"An error occurred while saving the Steam publish profile:\n\nDetails: {e}",
            )
            return False
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(
                self, "Save Error", f"An error occurred while saving:\n{e}"
            )
            return False
