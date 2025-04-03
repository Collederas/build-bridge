import os
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QStackedWidget,
    QFormLayout,
    QWidget,
    QLabel,
    QLineEdit,
    QTableWidget,
    QPushButton,
    QCheckBox,
    QFileDialog,
    QMessageBox,
    QComboBox,
    QListView,
    QHeaderView,
    QTableWidgetItem
)

from PyQt6.QtCore import Qt, QStringListModel

from vcs.p4client import P4Client
from app_config import ConfigManager


class SettingsDialog(QDialog):
    stores = ("Steam",)
    unreal_configurations = ["Development", "Shipping", "Test", "Debug"]
    unreal_platforms = ["Win64", "Win32",]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(600, 400)

        # Initialize config managers
        self.vcs_config_manager = ConfigManager("vcs")
        self.build_config_manager = ConfigManager("build")
        self.stores_config_manager = ConfigManager("stores")

        # Load configs through managers
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout()

        self.category_list = QListWidget()
        self.category_list.addItems(["Version Control", "Build", "Publish"])
        self.category_list.currentRowChanged.connect(self.switch_page)
        layout.addWidget(self.category_list, 1)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.create_vcs_page())
        self.stack.addWidget(self.create_unreal_build_page())
        self.stack.addWidget(self.create_publishing_page())

        layout.addWidget(self.stack, 3)

        button_layout = QHBoxLayout()
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self.apply_settings)
        button_layout.addWidget(apply_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

    def create_vcs_page(self):
        page = QWidget()
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # Get Perforce settings from ConfigManager
        p4port = self.vcs_config_manager.get("perforce.p4port", "")
        p4user = self.vcs_config_manager.get("perforce.p4user", "")
        p4client = self.vcs_config_manager.get("perforce.p4client", "")

        # Get password from keyring if user exists
        p4password = ""
        if p4user:
            p4password = self.vcs_config_manager.get_secure("BuildBridge", p4user) or ""

        self.p4user_input = QLineEdit(p4user)
        form_layout.addRow(QLabel("P4 User:"), self.p4user_input)

        self.p4password_input = QLineEdit(p4password)
        self.p4password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow(QLabel("P4 Password:"), self.p4password_input)

        self.p4port_input = QLineEdit(p4port)
        form_layout.addRow(QLabel("P4 Port:"), self.p4port_input)

        self.p4client_input = QLineEdit(p4client)
        form_layout.addRow(QLabel("P4 Client:"), self.p4client_input)

        layout.addLayout(form_layout)
        page.setLayout(layout)
        return page

    def create_unreal_build_page(self):
        page = QWidget()
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # Project setup section
        section_label = QLabel("Project Setup")
        section_label.setStyleSheet("font-weight: bold;")
        form_layout.addRow(section_label)

        # Engine path
        engine_path = self.build_config_manager.get("unreal.engine_path", "")
        self.engine_path_input = QLineEdit(engine_path)
        browse_engine_btn = QPushButton("Browse")
        browse_engine_btn.clicked.connect(self.browse_engine_path)

        engine_layout = QHBoxLayout()
        engine_layout.addWidget(self.engine_path_input)
        engine_layout.addWidget(browse_engine_btn)
        form_layout.addRow(QLabel("Engine Path:"), engine_layout)

        # Archive directory
        archive_dir = self.build_config_manager.get("unreal.archive_directory", "")
        self.archive_dir_input = QLineEdit(archive_dir)
        browse_archive_btn = QPushButton("Browse")
        browse_archive_btn.clicked.connect(self.browse_archive_path)

        archive_layout = QHBoxLayout()
        archive_layout.addWidget(self.archive_dir_input)
        archive_layout.addWidget(browse_archive_btn)
        form_layout.addRow(QLabel("Archive Directory:"), archive_layout)

        # Build configuration section
        build_section_label = QLabel("Build Configuration")
        build_section_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        form_layout.addRow(build_section_label)

        # Build type
        build_type = self.build_config_manager.get("unreal.build_type", "Development")
        self.build_type_combo = QComboBox()
        self.build_type_combo.addItems(self.unreal_configurations)
        self.build_type_combo.setCurrentText(build_type)
        form_layout.addRow(QLabel("Build Type:"), self.build_type_combo)

        # Target platform
        self.target_platforms_model = QStringListModel()
        stored_platforms = self.build_config_manager.get(
            "unreal.target_platforms", ["Win64"]
        )
        self.target_platforms_model.setStringList(stored_platforms)

        self.platform_selector = QComboBox()
        self.platform_selector.addItems(self.unreal_platforms)
        self.platform_selector.setCurrentText(
            stored_platforms[0] if stored_platforms else "Win64"
        )

        self.platforms_list = QListView()
        self.platforms_list.setModel(self.target_platforms_model)
        self.platforms_list.setMaximumHeight(80)

        platform_buttons_layout = QVBoxLayout()
        add_platform_btn = QPushButton("Add")
        add_platform_btn.clicked.connect(self.add_platform)
        remove_platform_btn = QPushButton("Remove")
        remove_platform_btn.clicked.connect(self.remove_platform)

        platform_buttons_layout.addWidget(add_platform_btn)
        platform_buttons_layout.addWidget(remove_platform_btn)
        platform_buttons_layout.addStretch()

        platform_layout = QHBoxLayout()

        # Platform selector with dropdown and add button together
        platform_selector_layout = QVBoxLayout()
        platform_selector_layout.addWidget(QLabel("Available Platforms:"))

        # Create a horizontal layout for the dropdown and Add button
        dropdown_add_layout = QHBoxLayout()
        dropdown_add_layout.addWidget(self.platform_selector)
        add_platform_btn = QPushButton("Add")
        add_platform_btn.clicked.connect(self.add_platform)
        dropdown_add_layout.addWidget(add_platform_btn)

        platform_selector_layout.addLayout(dropdown_add_layout)
        platform_layout.addLayout(platform_selector_layout)

        # Selected platforms list with remove button
        platforms_list_layout = QVBoxLayout()
        platforms_list_layout.addWidget(QLabel("Selected Platforms:"))

        # Create a horizontal layout for the list and Remove button
        list_remove_layout = QHBoxLayout()
        list_remove_layout.addWidget(self.platforms_list)
        remove_platform_btn = QPushButton("Remove")
        remove_platform_btn.clicked.connect(self.remove_platform)
        list_remove_layout.addWidget(remove_platform_btn)

        platforms_list_layout.addLayout(list_remove_layout)
        platform_layout.addLayout(platforms_list_layout)

        form_layout.addRow(QLabel("Target Platforms:"), platform_layout)

        # Cook settings section
        cook_section_label = QLabel("Cook Settings")
        cook_section_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        form_layout.addRow(cook_section_label)

        # Cook all checkbox
        cook_all = self.build_config_manager.get("unreal.cook_all", True)
        self.cook_all_checkbox = QCheckBox("Cook All Content")
        self.cook_all_checkbox.setChecked(cook_all)
        form_layout.addRow("", self.cook_all_checkbox)

        # Cook directories
        cook_dirs = self.build_config_manager.get("unreal.cook_dirs", [])
        cook_dirs_layout = QVBoxLayout()

        # Create list widget for cook directories
        self.cook_dirs_list = QListWidget()
        for directory in cook_dirs:
            self.cook_dirs_list.addItem(directory)
        self.cook_dirs_list.setFixedHeight(80)
        self.cook_dirs_list.setEnabled(not cook_all)
        cook_dirs_layout.addWidget(self.cook_dirs_list)

        # Add buttons for managing directories
        cook_dirs_buttons = QHBoxLayout()
        add_dir_btn = QPushButton("Add Directory")
        add_dir_btn.clicked.connect(self.add_cook_directory)
        add_dir_btn.setEnabled(not cook_all)
        cook_dirs_buttons.addWidget(add_dir_btn)

        remove_dir_btn = QPushButton("Remove Selected")
        remove_dir_btn.clicked.connect(self.remove_cook_directory)
        remove_dir_btn.setEnabled(not cook_all)
        cook_dirs_buttons.addWidget(remove_dir_btn)
        cook_dirs_layout.addLayout(cook_dirs_buttons)

        # Connect checkbox to enable/disable cook directory controls
        self.cook_all_checkbox.stateChanged.connect(
            lambda state: [
                self.cook_dirs_list.setEnabled(state != Qt.CheckState.Checked.value),
                add_dir_btn.setEnabled(state != Qt.CheckState.Checked.value),
                remove_dir_btn.setEnabled(state != Qt.CheckState.Checked.value)
            ]
        )

        form_layout.addRow(QLabel("Cook Directories:"), cook_dirs_layout)

        layout.addLayout(form_layout)
        page.setLayout(layout)
        return page

    def create_publishing_page(self):
        page = QWidget()
        layout = QVBoxLayout()

        self.store_checkboxes = {}
        self.store_forms = {}

        for store_name in self.stores:
            store_key = store_name.lower()
            is_enabled = self.stores_config_manager.get(f"{store_key}.enabled", False)

            checkbox = QCheckBox(f"Enable {store_name} Publishing")
            checkbox.setChecked(is_enabled)
            layout.addWidget(checkbox)
            self.store_checkboxes[store_name] = checkbox

            form_widget = QWidget()
            form_layout = QFormLayout()

            if store_name == "Steam":
                # App ID field
                app_id = QLineEdit(
                    self.stores_config_manager.get(f"{store_key}.app_id", "")
                )
                form_layout.addRow(QLabel("App ID:"), app_id)

                # Username field
                username = QLineEdit(
                    self.stores_config_manager.get(f"{store_key}.username", "")
                )
                form_layout.addRow(QLabel("Username:"), username)

                # Description field
                description = QLineEdit(
                    self.stores_config_manager.get(
                        f"{store_key}.description", "My Game Build v1.0"
                    )
                )
                form_layout.addRow(QLabel("Description:"), description)

                # Create a table for depot ID to path mapping
                depots_table = QTableWidget()
                depots_table.setColumnCount(3)  # Changed to 3 columns: ID, Path, Browse button
                depots_table.setHorizontalHeaderLabels(["Depot ID", "Path", ""])
                depots_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
                depots_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

                # Get depot mappings from config
                depot_mappings = self.stores_config_manager.get(f"{store_key}.depot_mappings", {})
                depots_table.setRowCount(len(depot_mappings) + 1)  # Extra row for new entries

                # Fill existing depot mappings
                row = 0
                for depot_id, path in depot_mappings.items():
                    depots_table.setItem(row, 0, QTableWidgetItem(depot_id))
                    depots_table.setItem(row, 1, QTableWidgetItem(path))
                    browse_btn = QPushButton("Browse")
                    browse_btn.clicked.connect(lambda _, r=row: self.browse_depot_path(depots_table, r))
                    depots_table.setCellWidget(row, 2, browse_btn)
                    row += 1

                # Add browse button to the empty row
                browse_btn = QPushButton("Browse")
                browse_btn.clicked.connect(lambda: self.browse_depot_path(depots_table, row))
                depots_table.setCellWidget(row, 2, browse_btn)

                # Add controls for managing depots
                depots_container = QWidget()
                depots_layout = QVBoxLayout(depots_container)
                depots_layout.addWidget(QLabel("Depot ID to Path Mapping:"))
                depots_layout.addWidget(depots_table)

                # Add/Remove buttons
                depot_buttons = QWidget()
                depot_buttons_layout = QHBoxLayout(depot_buttons)
                add_depot_btn = QPushButton("Add Row")
                add_depot_btn.clicked.connect(lambda: self.add_depot_row(depots_table))
                remove_depot_btn = QPushButton("Remove Selected")
                remove_depot_btn.clicked.connect(lambda: depots_table.removeRow(depots_table.currentRow()) 
                                            if depots_table.currentRow() >= 0 else None)
                depot_buttons_layout.addWidget(add_depot_btn)
                depot_buttons_layout.addWidget(remove_depot_btn)
                depot_buttons_layout.addStretch()

                depots_layout.addWidget(depot_buttons)
                form_layout.addRow("", depots_container)

                # Builder path field
                build_dir = os.getcwd()
                default_builder_path = os.path.normpath(
                    os.path.join(build_dir, "Steam/builder")
                )
                builder_path = QLineEdit(
                    self.stores_config_manager.get(
                        f"{store_key}.builder_path", default_builder_path
                    )
                )
                form_layout.addRow(QLabel("Builder Path:"), builder_path)

                # Browse button for builder path
                browse_btn = QPushButton("Browse")
                browse_btn.clicked.connect(
                    lambda _, p=builder_path: p.setText(
                        QFileDialog.getExistingDirectory(
                            self, "Select Builder Path", p.text()
                        )
                        or p.text()
                    )
                )
                form_layout.addRow("", browse_btn)

                self.store_forms[store_name] = {
                    "app_id": app_id,
                    "username": username,
                    "description": description,
                    "depots_table": depots_table,
                    "builder_path": builder_path,
                }

            # Rest of the method remains the same...
            form_widget.setLayout(form_layout)
            form_widget.setVisible(is_enabled)
            checkbox.stateChanged.connect(
                lambda state, w=form_widget: w.setVisible(
                    state == Qt.CheckState.Checked.value
                )
            )
            layout.addWidget(form_widget)

        layout.addStretch()
        page.setLayout(layout)
        return page

    def browse_depot_path(self, table, row):
        """Browse and set depot path for a specific row."""
        current_path = ""
        path_item = table.item(row, 1)
        if path_item:
            current_path = path_item.text()
        
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Depot Path", self.build_config_manager.get("unreal.archive_directory") or os.getcwd()
        )
        
        if dir_path:
            # Ensure there's a depot ID item
            if not table.item(row, 0):
                table.setItem(row, 0, QTableWidgetItem(""))
            table.setItem(row, 1, QTableWidgetItem(dir_path))

    def add_depot_row(self, table):
        """Add a new row with a browse button to the depots table."""
        row = table.rowCount()
        table.insertRow(row)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(lambda: self.browse_depot_path(table, row))
        table.setCellWidget(row, 2, browse_btn)

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)

    def save_vcs_settings(self) -> bool:
        """Save VCS settings and verify connection."""

        # Get user and password
        user = self.p4user_input.text().strip()
        password = self.p4password_input.text().strip()
        client = self.p4client_input.text().strip()
        port = self.p4port_input.text().strip()

        self.vcs_config_manager.set("perforce.p4user", user)
        self.vcs_config_manager.set("perforce.p4client", client)
        self.vcs_config_manager.set("perforce.p4port", port)
        self.vcs_config_manager.set_secure("BuildBridge", user, password)

        # Try to establish connection with the new settings
        try:
            # Test connection
            P4Client()

            # Save settings to file
            self.vcs_config_manager.save()
            return True

        except ConnectionError:
            QMessageBox.critical(
                self,
                "Connection Error",
                "Connection Error. Check your Perforce connection settings and retry.",
            )
        return False

    def browse_engine_path(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Unreal Engine Directory", self.engine_path_input.text()
        )
        if dir_path:
            self.engine_path_input.setText(dir_path)

    def browse_archive_path(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Archive Directory", self.archive_dir_input.text()
        )
        if dir_path:
            self.archive_dir_input.setText(dir_path)

    def add_platform(self):
        platform = self.platform_selector.currentText()
        current_platforms = self.target_platforms_model.stringList()

        if platform not in current_platforms:
            current_platforms.append(platform)
            self.target_platforms_model.setStringList(current_platforms)

    def remove_platform(self):
        selected_index = self.platforms_list.currentIndex()
        if selected_index.isValid():
            current_platforms = self.target_platforms_model.stringList()
            current_platforms.pop(selected_index.row())
            self.target_platforms_model.setStringList(current_platforms)


    def add_cook_directory(self):
        
        #TODO: Remove this hack and find a better way to get proj root
        try:
            p4 = P4Client()
            proj_dir = p4.get_workspace_root()
        except ConnectionError:
            pass

        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Content Directory", os.path.dirname(proj_dir)
        )

        if dir_path:
            # Check if directory already exists in the list
            exists = False
            for i in range(self.cook_dirs_list.count()):
                if self.cook_dirs_list.item(i).text() == dir_path:
                    exists = True
                    break
            
            if not exists:
                self.cook_dirs_list.addItem(dir_path)

    def remove_cook_directory(self):
        selected_items = self.cook_dirs_list.selectedItems()
        if not selected_items:
            return
            
        for item in selected_items:
            self.cook_dirs_list.takeItem(self.cook_dirs_list.row(item))

    def save_unreal_build_settings(self):
        """Save Unreal build settings."""
        # Save project setup settings
        self.build_config_manager.set(
            "unreal.engine_path", self.engine_path_input.text().strip()
        )
        self.build_config_manager.set(
            "unreal.archive_directory", self.archive_dir_input.text().strip()
        )

        # Save build configuration
        self.build_config_manager.set(
            "unreal.build_type", self.build_type_combo.currentText()
        )
        self.build_config_manager.set(
            "unreal.target_platforms", self.target_platforms_model.stringList()
        )

        # Save cook settings
        cook_dirs = []
        for i in range(self.cook_dirs_list.count()):
            cook_dirs.append(self.cook_dirs_list.item(i).text())
        self.build_config_manager.set("unreal.cook_dirs", cook_dirs)


        # Update UAT options
        uat_options = self.build_config_manager.get("unreal.build_uat_options", [])


        # Ensure clientconfig matches build type
        client_config_index = next(
            (
                i
                for i, opt in enumerate(uat_options)
                if opt.startswith("-clientconfig=")
            ),
            -1,
        )
        if client_config_index >= 0:
            uat_options[client_config_index] = (
                f"-clientconfig={self.build_type_combo.currentText()}"
            )
        else:
            uat_options.append(f"-clientconfig={self.build_type_combo.currentText()}")

        # Ensure archive directory is set
        archive_dir_index = next(
            (
                i
                for i, opt in enumerate(uat_options)
                if opt.startswith("-archivedirectory=")
            ),
            -1,
        )
        if archive_dir_index >= 0:
            uat_options[archive_dir_index] = (
                f"-archivedirectory={self.archive_dir_input.text().strip()}"
            )
        else:
            uat_options.append(
                f"-archivedirectory={self.archive_dir_input.text().strip()}"
            )

        # Make sure we have stage and archive options
        if "-stage" not in uat_options:
            uat_options.append("-stage")
        if "-archive" not in uat_options:
            uat_options.append("-archive")

        self.build_config_manager.set("unreal.build_uat_options", uat_options)


        # Save to file
        self.build_config_manager.save()

    def save_store_settings(self):
        """Save store settings."""
        for store_name, checkbox in self.store_checkboxes.items():
            store_key = store_name.lower()
            is_enabled = checkbox.isChecked()

            # Set enabled state in config
            self.stores_config_manager.set(f"{store_key}.enabled", is_enabled)

            # Handle specific store types
            if store_name == "Steam" and store_name in self.store_forms:
                form = self.store_forms[store_name]

                # Update store config
                self.stores_config_manager.set(
                    f"{store_key}.app_id", form["app_id"].text().strip()
                )
                self.stores_config_manager.set(
                    f"{store_key}.username", form["username"].text().strip()
                )
                self.stores_config_manager.set(
                    f"{store_key}.description", form["description"].text().strip()
                )

                # Save depot mappings
                depot_mappings = {}
                depots_table = form["depots_table"]
                for row in range(depots_table.rowCount()):
                    depot_id_item = depots_table.item(row, 0)
                    path_item = depots_table.item(row, 1)
                    
                    if depot_id_item and path_item and depot_id_item.text().strip():
                        depot_id = depot_id_item.text().strip()
                        path = path_item.text().strip()
                        depot_mappings[depot_id] = path
                
                self.stores_config_manager.set(f"{store_key}.depot_mappings", depot_mappings)

            elif store_name == "Epic" and store_name in self.store_forms:
                form = self.store_forms[store_name]
                self.stores_config_manager.set(
                    f"{store_key}.product_id", form["product_id"].text().strip()
                )
                self.stores_config_manager.set(
                    f"{store_key}.artifact_id", form["artifact_id"].text().strip()
                )

        # Save all store settings
        self.stores_config_manager.save()

    def apply_settings(self):
        # Save VCS settings and verify connection
        vcs_saved = self.save_vcs_settings()

        # Save store settings
        self.save_store_settings()

        # Save Unreal build settings
        self.save_unreal_build_settings()

        # Only accept if VCS connection was successful
        if vcs_saved:
            self.accept()