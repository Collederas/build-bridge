from genericpath import isdir
import os, logging
from turtle import pd
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QFileDialog,
    QCheckBox,
    QStackedWidget,
    QMessageBox,
    QWidget,
    QTableWidget,
    QAbstractItemView,
    QTableWidgetItem,
    QHeaderView
)

from PyQt6.QtGui import QIcon

from PyQt6.QtCore import Qt, pyqtSignal, QDir
from sqlalchemy import exists

from build_bridge.utils.paths import get_resource_path
from build_bridge.views.dialogs.settings_dialog import SettingsDialog

from build_bridge.core.vcs.p4client import P4Client
from build_bridge.models import (
    BuildTarget,
    Project,
    BuildTargetPlatformEnum,
    BuildTypeEnum,
    VCSTypeEnum,
)
from build_bridge.database import (
    SessionFactory,
)  # Assuming SessionFactory gives a session


class BuildTargetSetupDialog(QDialog):
    vcs_clients = {VCSTypeEnum.perforce: P4Client}
    build_target_created = pyqtSignal(int)

    def __init__(self, build_target_id: int = None):
        super().__init__()
        self.setWindowTitle("Build Target Setup")
        self.setMinimumSize(800, 500)
        icon_path = str(get_resource_path("build_bridge/icons/buildbridge.ico"))
        self.setWindowIcon(QIcon(icon_path))

        # Create session FIRST to query projects
        self.session = SessionFactory()

        if build_target_id:
            # Fetch existing target if ID is provided
            self.build_target = self.session.query(BuildTarget).get(build_target_id)
        else:
            self.build_target = None

        # Check for existing projects BEFORE trying to get/create one for the session
        self._initial_project_check()

        # Get or create project associated with this build target/session
        self.session_project = self.get_or_create_session_project(self.session)

        self.vcs_client = None
        self.vcs_connected = False

        # --- Create UI Elements ---
        # Create page 1 AFTER the initial project check
        self.page1 = self.create_page1()
        self.page2 = self.create_page2()

        self.stack = QStackedWidget()
        self.stack.addWidget(self.page1)
        self.stack.addWidget(self.page2)

        self.main_layout = QVBoxLayout()
        self.main_layout.addLayout(self.add_header("Build Target"))
        self.main_layout.addWidget(self.stack)
        self.main_layout.addLayout(self.create_footer())
        self.setLayout(self.main_layout)

        # Populate form fields AFTER UI is built
        self.initialize_form()

    def _initial_project_check(self):
        """Checks if any projects exist in the database."""
        try:
            self.projects_exist_initially = self.session.query(
                exists().where(Project.id != None)
            ).scalar()
            logging.info(
                f"Initial project check: {'Projects exist' if self.projects_exist_initially else 'No projects found'}"
            )
        except Exception as e:
            # Handle potential DB connection errors during the check
            logging.info(f"Error during initial project check: {e}")
            QMessageBox.critical(
                self, "Database Error", f"Could not check for existing projects:\n{e}"
            )
            self.projects_exist_initially = True  # Assume they exist to avoid locking user out? Or handle differently.

    def get_or_create_session_project(self, session):
        session_project = None
        if self.build_target and self.build_target.project:
            # If editing a target, use its project (make sure it's session-managed)
            session_project = session.merge(self.build_target.project)
        else:
            # If creating new, or target has no project, try finding the first project
            session_project = session.query(Project).first()
            if not session_project:
                # Only create a default *in memory* if none exist db-wide
                # The user should ideally add one via settings if none exist.
                # Don't add this default to the session automatically here.
                logging.info("No project found in DB or associated with build target.")
                # We will rely on the "Add Project" button flow if none exist.
                # Returning None here signifies no project is currently selected/available.
                return None 

        if session_project:
            # Ensure the found/merged project is in the session
            if session_project not in session:
                session.add(session_project)
            logging.info(
                f"Using project '{session_project.name}' - ID: {session_project.id} in the session."
            )
        return session_project

    def add_header(self, title_text):
        # (Keep existing code)
        title_layout = QHBoxLayout()
        title = QLabel(title_text)
        title.setStyleSheet("font-weight: bold; font-size: 18px;")
        title_layout.addWidget(title)
        return title_layout

    def create_page1(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Project section Label
        proj_label = QLabel("Project")
        proj_label.setStyleSheet("font-weight: bold; font-size: 18px;")
        layout.addWidget(proj_label)

        # === "Add Project" Button (conditionally visible) ===
        self.add_project_button = QPushButton("+ Add Project")
        self.add_project_button.clicked.connect(self._open_settings_to_add_project)
        # Visibility is set in _refresh_project_list / initialize_form
        layout.addWidget(self.add_project_button)
        # ===================================================

        # Project Form Layout (Combo, Source Dir)
        self.project_form_widget = QWidget()  # Put form in a widget to hide/show easily
        project_form = QFormLayout(self.project_form_widget)
        project_form.setContentsMargins(0, 0, 0, 0)  # Remove margins if needed

        self.project_combo = QComboBox()
        self.source_edit = QLineEdit()
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_folder)
        source_layout = QHBoxLayout()
        source_layout.addWidget(self.source_edit)
        source_layout.addWidget(browse_button)

        project_form.addRow("Project:", self.project_combo)
        project_form.addRow("Project Source", source_layout)

        # Add the form widget to the main page layout
        layout.addWidget(self.project_form_widget)

        layout.addSpacing(20)

        layout.addStretch()
        return widget

    def _open_settings_to_add_project(self):
        """Opens the SettingsDialog focused on adding a project."""
        logging.info("Opening Settings Dialog to add project...")
        settings_dialog = SettingsDialog(parent=self)
        try:
            # Navigate to the relevant page (index 1 as requested)
            # Adapt this call if your SettingsDialog uses a different method
            settings_dialog.setCurrentIndex(1)
        except AttributeError:
            logging.info(
                "Warning: SettingsDialog does not have setCurrentIndex method. Cannot navigate."
            )
        except Exception as e:
            logging.info(f"Warning: Could not navigate SettingsDialog: {e}")
        result = settings_dialog.exec()

        logging.info(f"Settings Dialog closed with result: {result}")
        # Refresh the project list in this dialog in case a project was added
        self._refresh_project_list()

    # --- Add/Refactor this method ---
    def _refresh_project_list(self):
        """Queries DB for projects, updates combo box, and sets visibility."""
        logging.info("Refreshing project list...")
        try:
            projects = self.session.query(Project).order_by(Project.name).all()
        except Exception as e:
            QMessageBox.critical(
                self, "Database Error", f"Failed to load projects:\n{e}"
            )
            projects = []  # Proceed with empty list on error

        self.project_combo.clear()

        if projects:
            self.project_combo.addItems([p.name for p in projects])

            # Try to re-select the current session project if it exists
            current_project_name = (
                self.session_project.name if self.session_project else None
            )
            index = -1
            if current_project_name:
                index = self.project_combo.findText(current_project_name)

            if index >= 0:
                self.project_combo.setCurrentIndex(index)
                # Update source dir based on selected project
                selected_project_obj = next(
                    (p for p in projects if p.name == current_project_name), None
                )
                if selected_project_obj:
                    self.source_edit.setText(selected_project_obj.source_dir or "")
                else:  # Should not happen if index was found, but defensively clear
                    self.source_edit.clear()

            elif projects:  # If current session project wasn't found/set, select first
                self.project_combo.setCurrentIndex(0)
                self.source_edit.setText(projects[0].source_dir or "")
                # Update self.session_project to the newly selected one
                self.session_project = projects[0]
                if self.session_project not in self.session:
                    self.session.add(self.session_project)
            else:
                self.source_edit.clear()

            # Show project form, hide 'Add' button
            self.project_form_widget.show()
            self.add_project_button.hide()
            logging.info(f"Loaded {len(projects)} projects into combo box.")

        else:
            self.project_combo.setEnabled(False)
            self.source_edit.clear()
            self.source_edit.setEnabled(False)
            self.project_form_widget.hide()
            self.add_project_button.show()
            self.session_project = None
            logging.info("No projects found. Showing 'Add Project' button.")

    def create_perforce_config_widget(self):
        widget = QWidget()
        layout = QFormLayout(widget)
        self.p4_user_edit = QLineEdit()
        self.p4_server_edit = QLineEdit()
        self.p4_client_edit = QLineEdit()
        self.p4_password_edit = QLineEdit()
        self.p4_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("User:", self.p4_user_edit)
        layout.addRow("Server Address:", self.p4_server_edit)
        layout.addRow("Client:", self.p4_client_edit)
        layout.addRow("Password:", self.p4_password_edit)
        return widget

    def create_page2(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        build_conf_label = QLabel("Build Config")
        build_conf_label.setStyleSheet("font-weight: bold; font-size: 18px;")
        layout.addWidget(build_conf_label)

        form = QFormLayout()
        self.build_type_combo = QComboBox()
        self.target_platform_combo = QComboBox()

        self.optimize_checkbox = QCheckBox("Optimize Packaging for Steam")
        self.optimize_hint = QLabel(
            "Will build using Valve\nRecommended padding alignment values"
        )
        self.optimize_hint.setStyleSheet("color: gray; font-size: 10px;")
        optimize_layout = QVBoxLayout()
        optimize_layout.addWidget(self.optimize_checkbox)
        optimize_layout.addWidget(self.optimize_hint)
        form.addRow("Build Type", self.build_type_combo)
        form.addRow("Target Platform", self.target_platform_combo)

        self.bt_ue_path_edit = QLineEdit("C:/Program Files/Epic Games")
        self.bt_ue_path_edit.setPlaceholderText("e.g., C:/Program Files/Epic Games")
        ue_path_layout = QHBoxLayout()
        ue_path_layout.addWidget(self.bt_ue_path_edit, 1)
        ue_browse_button = QPushButton("Browse")
        ue_browse_button.setToolTip(
            "Select the engine base path for this specific build target"
        )
        ue_browse_button.clicked.connect(self.browse_engine_path_for_target)
        ue_path_layout.addWidget(ue_browse_button)
        form.addRow("Unreal Engine Path:", ue_path_layout)

        ue_path_explanation = QLabel(
            "Provide the root directory containing engine versions (e.g., 'Epic Games'). "
            "The specific version (e.g., UE_5.3) will be detected from the .uproject file. "
            "Relies on standard engine folder names (UE_x.y)."
        )
        ue_path_explanation.setStyleSheet("color: gray; font-size: 9pt;") # Style as hint text
        ue_path_explanation.setWordWrap(True) # Allow text to wrap

        # Add the label on the next row, spanning both columns by providing an empty string for the label part
        form.addRow("", ue_path_explanation)

        # TARGET CONFIG
        target_layout = QHBoxLayout()
        target_label = QLabel("Target")
        browse_target_button = QPushButton("Browse")
        browse_target_button.clicked.connect(self.browse_target)
        self.target_value = QLineEdit(f"{self.session_project.source_dir}/MyTaget.Target.cs")
        target_layout.addWidget(target_label)
        target_layout.addWidget(self.target_value)
        target_layout.addWidget(browse_target_button)

        # MAPS
        self.maps_table = QTableWidget(0, 2)
        self.maps_table.setHorizontalHeaderLabels(["Path (Directory)", "Browse"])


        self.maps_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.maps_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.maps_table.horizontalHeader().setStretchLastSection(False)
        self.maps_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.maps_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.maps_table)
        layout.addLayout(self._create_maps_buttons(self.maps_table))
        # ---

        form.addRow(optimize_layout)
        form.addRow(target_layout)
        layout.addLayout(form)
        layout.addStretch()

        return widget

    def create_footer(self):
        footer_layout = QHBoxLayout()
        footer_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.page1_label = QLabel("1")
        self.page1_label.setStyleSheet(
            "background-color: black; color: white; padding: 4px 10px; border-radius: 10px;"
        )
        self.page1_label.mousePressEvent = self.page1_clicked
        self.page2_label = QLabel("2")
        self.page2_label.setStyleSheet("color: gray; margin-left: 8px;")
        self.page2_label.mousePressEvent = self.page2_clicked
        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.next_page)
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.accept)
        self.save_button.hide()
        footer_layout.addStretch()
        footer_layout.addWidget(self.page1_label)
        footer_layout.addWidget(self.page2_label)
        footer_layout.addSpacing(20)
        footer_layout.addWidget(self.next_button)
        footer_layout.addWidget(self.save_button)
        return footer_layout

    def page1_clicked(self, event):
        self.stack.setCurrentIndex(0)
        self.page1_label.setStyleSheet(
            "background-color: black; color: white; padding: 4px 10px; border-radius: 10px;"
        )
        self.page2_label.setStyleSheet("color: gray; margin-left: 8px;")
        self.next_button.show()
        self.save_button.hide()

    def page2_clicked(self, event):
        self.stack.setCurrentIndex(1)
        self.page1_label.setStyleSheet("color: gray; margin-right: 8px;")
        self.page2_label.setStyleSheet(
            "background-color: black; color: white; padding: 4px 10px; border-radius: 10px;"
        )
        self.next_button.hide()
        self.save_button.show()

    def next_page(self):
        if self.stack.currentIndex() == 0:
            # --- Validation before moving to next page ---
            if not self.session_project:
                QMessageBox.warning(
                    self,
                    "Project Required",
                    "Please add or select a project before proceeding.",
                )
                return  # Stay on page 1
            # --- End Validation ---
            self.page2_clicked(None)

    def _create_maps_buttons(self, target_table):
        """Helper function to create Add/Remove buttons for a specific map table."""
        layout = QHBoxLayout()
        add_button = QPushButton("Add Map")
        # Pass the target table to the slot
        add_button.clicked.connect(lambda: self._add_map_row(target_table))
        remove_button = QPushButton("Remove Selected Map")
        # Pass the target table to the slot
        remove_button.clicked.connect(lambda: self._remove_map_row())
        layout.addWidget(add_button)
        layout.addWidget(remove_button)
        layout.addStretch()
        return layout
    
    def _add_map_row(self, table_widget: QTableWidget):
        """Adds a new, empty row to the specified maps table."""
        self._insert_map_row(table_widget)
        table_widget.scrollToBottom()

    def _remove_map_row(self):
        """Removes the currently selected row from the maps table."""
        current_row = self.maps_table.currentRow()
        if current_row >= 0:
            self.maps_table.removeRow(current_row)
        else:
            QMessageBox.warning(
                self, "No Selection", "Please select a map row to remove."
            )

    def _insert_map_row(self, table_widget: QTableWidget, map_path=None):
        row = table_widget.rowCount()
        table_widget.insertRow(row)

        # Path item in column 0
        path_item = QTableWidgetItem(map_path or "")
        table_widget.setItem(row, 0, path_item)

        # Browse button in column 1
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(
            lambda checked=False, tbl=table_widget, r=row: self._browse_map_path(tbl, r)
        )
        table_widget.setCellWidget(row, 1, browse_button)

    def _load_maps_table(self, table_widget: QTableWidget, maps_dict: dict):
        """Load maps into the specified table."""
        print(f"MAP dict are: {maps_dict}")
        table_widget.setRowCount(0) # Clear existing rows
        if not isinstance(maps_dict, dict):
            logging.info(f"Warning: Maps data is not a dictionary: {maps_dict}")
            return
        for map_path in maps_dict.keys():
            print(f"MAPS are: {map_path}")
            self._insert_map_row(table_widget, map_path)

    def _browse_map_path(self, table_widget: QTableWidget, row):
        """Open a directory dialog to select a map path for the specified table."""
        current_path_item = table_widget.item(row, 1)
        start_dir = ""
        if current_path_item and current_path_item.text():
            start_dir = current_path_item.text()

        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter("UMAP Files (*.umap)")
        file_dialog.selectNameFilter("UMAP Files (*.umap)")
        file_dialog.setDirectory(os.path.dirname(start_dir))
        file_dialog.setOption(QFileDialog.Option.ReadOnly)
        if file_dialog.exec():
            table_widget.setItem(row, 0, QTableWidgetItem(file_dialog.selectedFiles()[0]))

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Project Folder", self.source_edit.text() or ""
        )
        if folder:
            self.source_edit.setText(folder)
    
    def browse_target(self):
        current_path = self.target_value.text().strip()
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter("Target.cs Files (*.Target.cs)")
        file_dialog.selectNameFilter("INI Files (*.Target.cs)")
        file_dialog.setDirectory(os.path.dirname(current_path))
        file_dialog.setOption(QFileDialog.Option.ReadOnly)
        if file_dialog.exec():
            self.target_value.setText(file_dialog.selectedFiles()[0])

    def browse_engine_path_for_target(self):
        """Opens a directory dialog to select the UE base path for this BuildTarget."""
        current_path = self.bt_ue_path_edit.text()
        start_dir = current_path if os.path.isdir(current_path) else QDir.homePath()

        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Unreal Engine Base Directory for this Build Target",
            start_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
        )
        if directory:
            self.bt_ue_path_edit.setText(directory)

    def initialize_form(self):
        # --- Refresh Project List and set visibility ---
        self._refresh_project_list()

        # --- Initialize Page 2 fields ---
        self.build_type_combo.clear()
        self.build_type_combo.addItems([e.value for e in BuildTypeEnum])
        current_build = BuildTypeEnum.prod.value
        if self.build_target and self.build_target.build_type:
            current_build = self.build_target.build_type.value
        self.build_type_combo.setCurrentText(current_build)

        self.target_platform_combo.clear()
        self.target_platform_combo.addItems([p.value for p in BuildTargetPlatformEnum])
        current_platform = BuildTargetPlatformEnum.win_64.value  # Default
        if self.build_target and self.build_target.target_platform:
            current_platform = (
                self.build_target.target_platform.value
            )  # Note: Enum value already stored
        self.target_platform_combo.setCurrentText(current_platform)

        self.bt_ue_path_edit.setText(self.build_target.unreal_engine_base_path)
        
        if not self.build_target.target:
            self.target_value.setText(f"{self.session_project.source_dir}/MyTarget.Target.cs")
        else:
            self.target_value.setText(self.build_target.target)

        self.optimize_checkbox.setChecked(
            bool(self.build_target.optimize_for_steam) if self.build_target else True
        )
        maps = self.build_target.maps or {}

        map_id = next(iter(maps))
        maps[map_id] = map_id

        self._load_maps_table(self.maps_table, maps)

    def _collect_and_validate_maps(self, table_widget: QTableWidget):
        """ Helper to collect and validate maps from a specific table.
            Returns a dictionary of maps or None if validation fails.
        """
        maps_to_save = {}
        for row in range(table_widget.rowCount()):
            path_item = table_widget.item(row, 0)

            if not path_item or not path_item.text().strip():
                QMessageBox.warning(self, "Validation Error", f"Map Path is missing in row {row+1}.")
                table_widget.selectRow(row)
                table_widget.setFocus()
                return None 

            map_path = path_item.text().strip()

            maps_to_save[map_path] = map_path
        return maps_to_save

    def accept(self):
        try:
            # --- Crucial check: Ensure a project is selected ---
            if not self.session_project:
                # This might happen if the user somehow gets to save without a project
                # (e.g., if validation in next_page is bypassed)
                QMessageBox.critical(
                    self, "Error", "No project selected or available. Cannot save."
                )
                self.stack.setCurrentIndex(0)  # Go back to page 1
                return  # Do not proceed

            # Find the selected project object from the DB using the combo box text
            selected_project_name = self.project_combo.currentText()
            selected_project = (
                self.session.query(Project)
                .filter_by(name=selected_project_name)
                .first()
            )

            if not selected_project:
                # Should not happen if combo is populated correctly, but good to check
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Selected project '{selected_project_name}' not found in database.",
                )
                return

            # --- Update project details ---
            selected_project.source_dir = self.source_edit.text().strip()
            # Add the project to session if it wasn't already (merge does this implicitly)
            # Or make sure self.session_project points to the *correct* selected one
            self.session_project = self.session.merge(selected_project)

            # --- Create or update BuildTarget ---
            if not self.build_target:
                self.build_target = BuildTarget(project=self.session_project)
                self.session.add(self.build_target)
            else:
                # Ensure existing build_target is associated with the selected project
                self.build_target.project = self.session_project

            self.build_target.build_type = BuildTypeEnum(
                self.build_type_combo.currentText()
            )
            self.build_target.target_platform = BuildTargetPlatformEnum(
                self.target_platform_combo.currentText()
            )

            self.build_target.target = self.target_value.text().strip()

            ue_path_text = self.bt_ue_path_edit.text().strip()
            self.build_target.unreal_engine_base_path = (
                ue_path_text if ue_path_text else "C:/Program Files/Epic Games"
            )

            self.build_target.optimize_for_steam = self.optimize_checkbox.isChecked()

            maps = self._collect_and_validate_maps(self.maps_table)
            self.build_target.maps = maps

            self.session.commit()
            logging.info(
                f"BuildTarget {self.build_target.id} - Project '{self.session_project.name}' - {self.build_target.target_platform.value} saved."
            )
            self.build_target_created.emit(self.build_target.id)
            super().accept()  # Close dialog only on successful commit

        except Exception as e:
            self.session.rollback()
            logging.info(f"Save failed: {str(e)}")  # Log detailed error
            QMessageBox.critical(self, "Error", f"Failed to save:\n{str(e)}")
            # Don't reject automatically, let the user fix the issue or cancel

    def reject(self):
        logging.info("Rolling back session and closing dialog.")
        self.session.rollback()
        self.session.close()
        if self.vcs_client:
            self.vcs_client._disconnect()
        super().reject()

    def closeEvent(self, event):
        # Check if session is still active and has changes
        is_dirty = False
        try:
            if self.session.is_active:
                is_dirty = (
                    bool(self.session.dirty)
                    or bool(self.session.new)
                    or bool(self.session.deleted)
                )
        except Exception:
            pass  # Ignore errors if session is already closed etc.

        if is_dirty:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Close anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,  # Default to No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.reject()  # Rollback and close session properly
                event.accept()
            else:
                event.ignore()
        else:
            self.reject()  # Close session even if not dirty
            event.accept()
