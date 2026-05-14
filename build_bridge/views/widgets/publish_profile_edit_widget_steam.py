import copy
import logging
import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
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

from build_bridge.models import SteamConfig, SteamPublishProfile
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
        main_layout = QVBoxLayout(self)
        common_form_layout = QFormLayout()

        # Read-only build target label
        target_name = ""
        if self.publish_profile.build_target:
            target_name = self.publish_profile.build_target.name or ""
        self.target_name_label = QLabel(target_name or "—")
        common_form_layout.addRow("Build Target:", self.target_name_label)

        self.builder_path_display = QLineEdit()
        self.builder_path_display.setReadOnly(True)
        self.builder_path_display.setToolTip(
            "Managed by Build Bridge. This is where Steam config files and upload logs will go."
        )
        common_form_layout.addRow("Builder Path:", self.builder_path_display)

        main_layout.addLayout(common_form_layout)

        self.app_id_input = QSpinBox()
        self.app_id_input.setRange(0, 9999999)
        self.app_id_input.setToolTip("The Steam App ID for your main game.")
        common_form_layout.addRow("App ID:", self.app_id_input)

        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("Main, Demo, QA, ...")
        common_form_layout.addRow("Profile Name:", self.description_input)

        self.depots_table = self._create_depots_table()
        main_layout.addWidget(self.depots_table)
        main_layout.addLayout(self._create_depot_buttons(self.depots_table))

        auth_layout = QHBoxLayout()
        self.auth_combo = QComboBox()
        self.auth_combo.setToolTip("Select the Steam account to use for publishing.")
        auth_layout.addWidget(self.auth_combo)
        common_form_layout.addRow("Steam Auth:", auth_layout)

        self.steam_config_button = QPushButton("Manage Steam Configuration")
        self.steam_config_button.clicked.connect(self._open_steam_settings)
        main_layout.addWidget(self.steam_config_button)

        self.setLayout(main_layout)

    def _populate_fields(self):
        with self.session.no_autoflush:
            self._refresh_auth_options()
            self._update_builder_path()

            app_id = self.publish_profile.app_id or 0
            self.app_id_input.setValue(app_id)

            profile_name = self.publish_profile.description or "Main"
            self.description_input.setText(profile_name)

            depots = copy.deepcopy(self.publish_profile.depots or {})
            self._load_depots_table(self.depots_table, depots)

    def _update_builder_path(self):
        path = "N/A"
        try:
            if self.publish_profile.build_target:
                path = self.publish_profile.builder_path or "N/A"
        except Exception as e:
            path = f"Error: {e}"
        self.builder_path_display.setText(str(path))

    def _refresh_auth_options(self):
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
            QMessageBox.critical(self, "Database Error", f"Failed to load Steam Config: {e}")
            self.auth_combo.setEnabled(False)

    def _create_depots_table(self):
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Depot ID", "Path (Directory)", "Browse"])
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        return table

    def _create_depot_buttons(self, target_table):
        layout = QHBoxLayout()
        add_button = QPushButton("Add Depot")
        add_button.clicked.connect(lambda: self._add_depot_row(target_table))
        remove_button = QPushButton("Remove Selected Depot")
        remove_button.clicked.connect(lambda: self._remove_depot_row())
        layout.addWidget(add_button)
        layout.addWidget(remove_button)
        layout.addStretch()
        return layout

    def _load_depots_table(self, table_widget: QTableWidget, depots_dict: dict):
        table_widget.setRowCount(0)
        if not isinstance(depots_dict, dict):
            logging.info(f"Warning: Depots data is not a dictionary: {depots_dict}")
            return
        for depot_id, depot_path in depots_dict.items():
            self._insert_depot_row(table_widget, depot_id, depot_path)

    def _insert_depot_row(self, table_widget: QTableWidget, depot_id=None, depot_path=None):
        row = table_widget.rowCount()
        table_widget.insertRow(row)

        id_item = QTableWidgetItem(str(depot_id) if depot_id is not None else "")
        table_widget.setItem(row, 0, id_item)

        path_item = QTableWidgetItem(depot_path or "")
        table_widget.setItem(row, 1, path_item)

        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(
            lambda checked=False, tbl=table_widget, r=row: self._browse_depot_path(tbl, r)
        )
        table_widget.setCellWidget(row, 2, browse_button)

    def _add_depot_row(self, table_widget: QTableWidget):
        self._insert_depot_row(table_widget)
        table_widget.scrollToBottom()

    def _remove_depot_row(self):
        current_row = self.depots_table.currentRow()
        if current_row >= 0:
            self.depots_table.removeRow(current_row)
        else:
            QMessageBox.warning(self, "No Selection", "Please select a depot row to remove.")

    def _browse_depot_path(self, table_widget: QTableWidget, row):
        current_path_item = table_widget.item(row, 1)
        start_dir = ""
        if current_path_item and current_path_item.text():
            start_dir = current_path_item.text()
        elif self.publish_profile.build_target and self.publish_profile.build_target.builds_path:
            start_dir = str(self.publish_profile.build_target.builds_path)

        path = QFileDialog.getExistingDirectory(self, "Select Depot Directory", start_dir)
        if path:
            table_widget.setItem(row, 1, QTableWidgetItem(path))

    def _open_steam_settings(self):
        settings = settings_dialog.SettingsDialog(default_page=1)
        settings.exec()
        self._refresh_auth_options()

    def _collect_and_validate_depots(self, table_widget: QTableWidget):
        depots_to_save = {}
        for row in range(table_widget.rowCount()):
            id_item = table_widget.item(row, 0)
            path_item = table_widget.item(row, 1)

            if not id_item or not id_item.text().strip():
                QMessageBox.warning(self, "Validation Error", f"Depot ID is missing in row {row+1}.")
                table_widget.selectRow(row)
                table_widget.setFocus()
                return None
            if not path_item or not path_item.text().strip():
                QMessageBox.warning(self, "Validation Error", f"Depot Path is missing in row {row+1}.")
                table_widget.selectRow(row)
                table_widget.setFocus()
                return None

            try:
                depot_id = int(id_item.text().strip())
                if depot_id <= 0:
                    raise ValueError("Depot ID must be positive")
            except ValueError:
                QMessageBox.warning(self, "Validation Error",
                                     f"Invalid Depot ID '{id_item.text()}' in row {row+1}. Must be a positive integer.")
                table_widget.selectRow(row)
                table_widget.editItem(id_item)
                return None

            depot_path = path_item.text().strip()
            if not os.path.exists(depot_path):
                QMessageBox.warning(self, "Validation Error",
                                     f"Depot path in row {row+1} does not exist:\n{depot_path}")
                table_widget.selectRow(row)
                table_widget.setFocus()
                return None

            if depot_id in depots_to_save:
                QMessageBox.warning(self, "Validation Error",
                                     f"Duplicate Depot ID '{depot_id}' found in row {row+1}.")
                table_widget.selectRow(row)
                table_widget.editItem(id_item)
                return None

            depots_to_save[depot_id] = depot_path
        return depots_to_save

    def save_profile(self):
        if not self.publish_profile:
            QMessageBox.critical(self, "Error", "Cannot save, profile data is missing.")
            return False

        selected_auth_id = self.auth_combo.currentData()
        if selected_auth_id is None:
            QMessageBox.warning(self, "Validation Error", "Please select a Steam Authentication account.")
            self.auth_combo.setFocus()
            return False

        profile_name = self.description_input.text().strip()
        if not profile_name:
            QMessageBox.warning(self, "Validation Error", "Please enter a Profile Name.")
            self.description_input.setFocus()
            return False

        app_id = self.app_id_input.value()
        if app_id <= 0:
            QMessageBox.warning(self, "Validation Error", "Please enter a valid App ID (must be > 0).")
            self.app_id_input.setFocus()
            return False

        regular_depots = self._collect_and_validate_depots(self.depots_table)
        if regular_depots is None:
            return False

        try:
            if not object_session(self.publish_profile):
                self.session.add(self.publish_profile)

            self.publish_profile.steam_config_id = selected_auth_id
            self.publish_profile.app_id = app_id
            self.publish_profile.description = profile_name
            self.publish_profile.depots = regular_depots

            self.session.commit()
            self.profile_saved_signal.emit()
            QMessageBox.information(self, "Success", "Steam profile saved successfully.")
            return True

        except AttributeError as e:
            self.session.rollback()
            QMessageBox.critical(self, "Save Error", f"Error saving Steam publishing configuration:\n{e}")
            return False
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Save Error", f"An error occurred while saving:\n{e}")
            return False
