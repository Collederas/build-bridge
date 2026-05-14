import logging

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QComboBox,
)

from PyQt6.QtCore import pyqtSignal
from sqlalchemy.orm import object_session

from build_bridge.database import session_scope
from build_bridge.exceptions import InvalidConfigurationError
from build_bridge.core.publisher.itch.itch_publisher import (
    validate_itch_channel,
    validate_itch_target,
)
from build_bridge.models import ItchConfig, ItchPublishProfile
from build_bridge.views.dialogs import settings_dialog


class ItchPublishProfileWidget(QWidget):
    profile_saved_signal = pyqtSignal()

    def __init__(self, publish_profile: ItchPublishProfile, session, parent=None):
        self.publish_profile = publish_profile
        self.session = session

        super().__init__(parent=parent)

        self._init_ui()
        self._populate_fields()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Read-only build target label
        target_name = ""
        if self.publish_profile.build_target:
            target_name = self.publish_profile.build_target.name or ""
        self.target_name_label = QLabel(target_name or "—")
        form_layout.addRow("Build Target:", self.target_name_label)

        self.user_game_id_input = QLineEdit()
        self.user_game_id_input.setPlaceholderText("username/game-slug")
        self.user_game_id_input.setToolTip("Format: username/game-slug")
        form_layout.addRow("User/Game ID:", self.user_game_id_input)

        self.channel_name_input = QLineEdit()
        self.channel_name_input.setPlaceholderText("default-channel")
        self.channel_name_input.setToolTip("The channel name for publishing (e.g., windows-beta)")
        form_layout.addRow("Channel Name:", self.channel_name_input)

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
        with self.session.no_autoflush:
            if not self.publish_profile:
                QMessageBox.critical(self, "Error", "Profile data is not available.")
                return

            self._refresh_auth_options()

            existing_channel = self.publish_profile.itch_channel_name
            channel_name = ""

            if existing_channel and existing_channel != "":
                channel_name = existing_channel
            else:
                bt = self.publish_profile.build_target
                if bt and bt.target_platform:
                    try:
                        channel_name = bt.target_platform.value.lower()
                    except Exception:
                        pass

            self.channel_name_input.setText(channel_name)

            existing_game_id = self.publish_profile.itch_user_game_id
            game_id = ""

            if existing_game_id and existing_game_id != "":
                game_id = existing_game_id
            else:
                conf = self.session.query(ItchConfig).one_or_none()
                project = self.publish_profile.project
                if conf and project:
                    game_id = f"{conf.username}/{project.name.lower().replace(' ', '-')}"

            self.user_game_id_input.setText(game_id)

    def _open_itch_settings(self):
        settings = settings_dialog.SettingsDialog(default_page=2)
        settings.exec()
        self._refresh_auth_options()

    def _refresh_auth_options(self):
        self.auth_combo.clear()
        current_itch_config_id = getattr(self.publish_profile, "itch_config_id", None)

        with session_scope() as session:
            itch_configs = (
                session.query(ItchConfig).order_by(ItchConfig.username.asc()).all()
            )

            try:
                if not itch_configs:
                    self.auth_combo.addItem("No Itch.io accounts configured", None)
                    self.auth_combo.setEnabled(False)
                else:
                    self.auth_combo.setEnabled(True)
                    self.auth_combo.addItem("Select Auth Profile...", None)
                    for itch_config in itch_configs:
                        self.auth_combo.addItem(itch_config.username, itch_config.id)

                if current_itch_config_id is not None:
                    selected_index = self.auth_combo.findData(current_itch_config_id)
                    self.auth_combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
                else:
                    self.auth_combo.setCurrentIndex(1 if len(itch_configs) == 1 else 0)

            except Exception as e:
                QMessageBox.critical(self, "Database Error",
                                      f"Failed to load Itch.io authentications: {e}")
                self.auth_combo.setEnabled(False)

    def save_profile(self):
        if not self.publish_profile:
            QMessageBox.critical(self, "Error", "Cannot save, profile data is missing.")
            return False

        selected_auth_id = self.auth_combo.currentData()
        if selected_auth_id is None:
            QMessageBox.warning(self, "Validation Error",
                                  "Please select an Itch.io Authentication account.")
            self.auth_combo.setFocus()
            return False

        selected_auth = self.session.get(ItchConfig, selected_auth_id)
        user_game_id = self.user_game_id_input.text().strip()
        channel_name = self.channel_name_input.text().strip()
        try:
            validate_itch_target(user_game_id, selected_auth.username if selected_auth else None)
            validate_itch_channel(channel_name)
        except InvalidConfigurationError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
            self.user_game_id_input.setFocus()
            return False

        try:
            if not object_session(self.publish_profile):
                self.session.add(self.publish_profile)

            self.publish_profile.description = self._default_description()
            self.publish_profile.itch_user_game_id = user_game_id
            self.publish_profile.itch_channel_name = channel_name
            self.publish_profile.itch_config_id = selected_auth_id

            self.session.commit()
            self.profile_saved_signal.emit()
            QMessageBox.information(self, "Success", "Itch.io publishing configuration saved.")
            return True

        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Save Error", f"An error occurred while saving:\n{e}")
            return False

    def _default_description(self):
        target = self.publish_profile.build_target
        if target and target.name:
            return target.name
        project = self.publish_profile.project
        if project and project.name:
            return project.name
        return "Itch.io"
