import os, logging

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
    QDialog,
    QStyle,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from build_bridge.models import (
    Build,
    BuildTarget,
    Project,
    PublishProfile,
    StoreEnum,
)
from build_bridge.core.publisher.itch.itch_publisher import ItchPublisher
from build_bridge.core.preflight import validate_publish_preflight
from build_bridge.database import SessionFactory
from build_bridge.exceptions import InvalidConfigurationError
from build_bridge.core.publisher.steam.steam_publisher import SteamPublisher
from build_bridge.views.dialogs.preflight_dialog import PreflightDialog
from build_bridge.views.dialogs.publish_profile_manager_dialog import (
    PublishProfileManagerDialog,
)


class PublishProfileListWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.session = SessionFactory()

        self.setWindowTitle("Available Builds")
        self.setGeometry(100, 100, 600, 400)
        self.setMinimumSize(500, 300)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.addStretch(1)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("ghostButton")
        self.refresh_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )
        self.refresh_button.setToolTip("Refresh the builds list from the database")
        self.refresh_button.clicked.connect(self.refresh_builds)
        self.refresh_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        toolbar_layout.addWidget(self.refresh_button)
        main_layout.addLayout(toolbar_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVisible(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.scroll_area.setMinimumHeight(100)

        self.scroll_content = QWidget()
        self.vbox = QVBoxLayout(self.scroll_content)
        self.vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.vbox.setContentsMargins(0, 0, 0, 0)
        self.vbox.setSpacing(8)
        self.scroll_area.setWidget(self.scroll_content)

        self.empty_message_label = QLabel("No builds available.")
        self.empty_message_label.setObjectName("emptyState")
        self.empty_message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_message_label.setVisible(True)
        self.empty_message_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        main_layout.addWidget(self.scroll_area)
        main_layout.addWidget(self.empty_message_label)

        self.refresh_builds()

    def refresh_builds(self):
        """Re-queries the DB and rebuilds the builds list."""
        while self.vbox.count():
            child = self.vbox.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        try:
            self.session.expire_all()
            project = self.session.query(Project).first()
            if not project:
                self.empty_message_label.setText("No project configured.")
                self.empty_message_label.setVisible(True)
                self.scroll_area.setVisible(False)
                return

            builds = (
                self.session.query(Build)
                .join(BuildTarget)
                .filter(BuildTarget.project_id == project.id)
                .order_by(Build.created_at.desc())
                .all()
            )

        except Exception as e:
            logging.info(f"Error querying builds: {e}", exc_info=True)
            self.empty_message_label.setText("Error loading builds.")
            self.empty_message_label.setVisible(True)
            self.scroll_area.setVisible(False)
            return

        if not builds:
            self.empty_message_label.setText("No builds available.")
            self.empty_message_label.setVisible(True)
            self.scroll_area.setVisible(False)
            return

        self.scroll_area.setVisible(True)
        self.empty_message_label.setVisible(False)

        for build in builds:
            widget = PublishProfileEntry(build=build, session=self.session)
            self.vbox.addWidget(widget)

        self.vbox.addStretch(1)

    def closeEvent(self, a0):
        self.session.close()
        return super().closeEvent(a0)


class PublishProfileEntry(QWidget):
    store_publishers = {StoreEnum.itch: ItchPublisher, StoreEnum.steam: SteamPublisher}

    def __init__(self, build: Build, session):
        super().__init__()
        self.build = build
        self.build_root = build.output_path
        self.build_id = build.version  # kept for compatibility with existing label references
        self.publish_profile: PublishProfile | None = None
        self.session = session

        self.setObjectName("buildCard")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(14, 12, 14, 12)
        self.main_layout.setSpacing(9)

        # First row: build name + store selector
        self.top_row = QHBoxLayout()
        self.top_row.setSpacing(14)

        display_name_font = QFont()
        display_name_font.setBold(True)

        target_name = ""
        try:
            target_name = build.build_target.name if build.build_target else ""
        except Exception:
            pass

        self.display_name_label = QLabel(f"{target_name} — {build.version}")
        self.display_name_label.setObjectName("primaryText")
        self.display_name_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.display_name_label.setWordWrap(True)
        self.display_name_label.setFont(display_name_font)
        self.top_row.addWidget(self.display_name_label)

        platform_widget = QWidget()
        platform_layout = QHBoxLayout(platform_widget)
        platform_layout.setContentsMargins(0, 0, 0, 0)
        platform_layout.setSpacing(5)

        store_label = QLabel("Store")
        store_label.setObjectName("fieldLabel")
        store_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        platform_layout.addWidget(store_label)

        self.store_type_combo = QComboBox()
        self.store_type_combo.setMinimumWidth(100)
        self.store_type_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        for store_enum in self.store_publishers.keys():
            self.store_type_combo.addItem(str(store_enum.value), store_enum)
        self.store_type_combo.setToolTip("Select the target platform for publishing this build")
        platform_layout.addWidget(self.store_type_combo)

        platform_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.top_row.addWidget(platform_widget)
        self.top_row.addStretch(1)
        self.main_layout.addLayout(self.top_row)

        # Second row: selected publish profile
        self.profile_row = QHBoxLayout()
        self.profile_row.setSpacing(8)
        profile_label = QLabel("Publish profile")
        profile_label.setObjectName("fieldLabel")
        self.profile_row.addWidget(profile_label)

        self.profile_value_label = QLabel("No profile selected")
        self.profile_value_label.setObjectName("primaryText")
        self.profile_value_label.setWordWrap(True)
        self.profile_row.addWidget(self.profile_value_label, 1)

        self.manage_profiles_button = QPushButton("Change...")
        self.manage_profiles_button.setObjectName("ghostButton")
        self.manage_profiles_button.setToolTip("Create, select, rename, edit, or delete publish profiles")
        self.manage_profiles_button.clicked.connect(self.manage_publish_profiles)
        self.profile_row.addWidget(self.manage_profiles_button)
        self.main_layout.addLayout(self.profile_row)

        # Third row: action buttons
        self.bottom_row = QHBoxLayout()
        self.bottom_row.setSpacing(10)
        self.bottom_row.addStretch(1)

        browse_archive_button = QPushButton("Browse")
        browse_archive_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        browse_archive_button.setToolTip(f"Open build folder:\n{self.build_root}")
        browse_archive_button.clicked.connect(self.browse_archive_directory)
        self.bottom_row.addWidget(browse_archive_button)

        self.publish_button = QPushButton("Publish")
        self.publish_button.setObjectName("primaryButton")
        self.publish_button.clicked.connect(self.handle_publish)
        self.bottom_row.addWidget(self.publish_button)
        self.main_layout.addLayout(self.bottom_row)

        self.store_type_combo.currentIndexChanged.connect(self.on_store_changed)
        self.on_store_changed()

    def update_publish_button_enabled(self):
        ready = self.store_type_combo.currentData() is not None and self.publish_profile is not None
        self.publish_button.setEnabled(ready)
        self._refresh_publish_tooltip()

    def on_store_changed(self):
        self._load_default_publish_profile()
        self.update_publish_button_enabled()

    def on_publish_profile_added_or_updated(self):
        self._load_default_publish_profile(
            selected_profile_id=getattr(self.publish_profile, "id", None)
        )
        self.update_publish_button_enabled()

    def _get_profile_label(self, profile: PublishProfile):
        if profile.description and profile.description.strip():
            return profile.description.strip()
        return f"Profile #{profile.id}"

    def _load_default_publish_profile(self, selected_profile_id=None):
        selected_store_enum = self.store_type_combo.currentData()
        if selected_store_enum is None:
            self.publish_profile = None
            self._refresh_profile_summary()
            return

        try:
            self.session.refresh(self.build)
            profiles = [
                p for p in self.build.build_target.publish_profiles
                if p.store_type == selected_store_enum
            ]
            profiles.sort(key=lambda p: p.id)
        except Exception as e:
            logging.info(f"Error loading publish profiles: {e}")
            profiles = []

        self.publish_profile = None
        if profiles:
            if selected_profile_id is not None:
                self.publish_profile = next(
                    (p for p in profiles if p.id == selected_profile_id), None
                )
            if self.publish_profile is None:
                self.publish_profile = profiles[0]

        self._refresh_profile_summary()

    def _refresh_profile_summary(self):
        if self.publish_profile is None:
            selected_store_enum = self.store_type_combo.currentData()
            store_label = selected_store_enum.value if selected_store_enum else "store"
            self.profile_value_label.setText(f"No {store_label} profile selected")
            self.profile_value_label.setToolTip("Use Change... to create or select one.")
        else:
            profile_label = self._get_profile_label(self.publish_profile)
            self.profile_value_label.setText(profile_label)
            self.profile_value_label.setToolTip(f"Selected publish profile: {profile_label}")

    def _on_profile_selected_from_manager(self, profile):
        if profile is None:
            self.publish_profile = None
        else:
            self.publish_profile = self.session.merge(profile)
        self._refresh_profile_summary()
        self.update_publish_button_enabled()

    def manage_publish_profiles(self):
        selected_platform_enum = self.store_type_combo.currentData()
        if selected_platform_enum is None:
            QMessageBox.information(self, "Select Store", "Please select a store before managing publish profiles.")
            return

        manager = PublishProfileManagerDialog(
            session=self.session,
            build_target_id=self.build.build_target_id,
            store_type=selected_platform_enum,
            selected_profile_id=getattr(self.publish_profile, "id", None),
            parent=self,
        )
        manager.profile_selected_signal.connect(self._on_profile_selected_from_manager)
        manager.profiles_changed_signal.connect(self.on_publish_profile_added_or_updated)
        manager.exec()

        if self.publish_profile is None:
            self._load_default_publish_profile()
        else:
            self.publish_profile = self.session.get(PublishProfile, self.publish_profile.id)
            self._refresh_profile_summary()
        self.update_publish_button_enabled()

    def _refresh_publish_tooltip(self):
        selected_platform_enum = self.store_type_combo.currentData()
        if self.publish_profile is None:
            store_label = selected_platform_enum.value if selected_platform_enum else "store"
            self.publish_button.setToolTip(f"Create or select a {store_label} publish profile first.")
            return

        try:
            publisher_class = self.store_publishers.get(selected_platform_enum)
            if not publisher_class:
                raise InvalidConfigurationError(
                    f"No publisher implementation found for {selected_platform_enum.value}"
                )

            if selected_platform_enum == StoreEnum.steam:
                publisher_instance = publisher_class(publish_profile=self.publish_profile)
            else:
                publisher_instance = publisher_class(publish_profile=self.publish_profile)

            publisher_instance.validate_publish_profile()
            self.publish_button.setToolTip(
                f"Publish build '{self.build_id}' to {selected_platform_enum.value}"
            )

        except InvalidConfigurationError as e:
            self.publish_button.setToolTip(f"Cannot publish: {e}")
        except Exception as e:
            self.publish_button.setToolTip(f"Unexpected validation error: {e}")
            logging.info(f"Unexpected validation error: {e}")

    def validate_build_content(self):
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
            raise InvalidConfigurationError(f"Error accessing build directory content: {e}")

    def browse_archive_directory(self):
        if self.build_root and os.path.isdir(self.build_root):
            try:
                if os.name == "nt":
                    os.startfile(self.build_root)
                else:
                    import subprocess
                    subprocess.Popen(["open", self.build_root])
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not open directory:\n{self.build_root}\n\nError: {e}")
        else:
            QMessageBox.warning(self, "Error", f"Build directory not found or invalid:\n{self.build_root}")

    def handle_publish(self):
        selected_store_enum = self.store_type_combo.currentData()
        if selected_store_enum is None:
            QMessageBox.warning(self, "Error", "No target platform selected.")
            return
        if self.publish_profile is None:
            QMessageBox.information(self, "Select Profile",
                                     "Create or select a publish profile before publishing.")
            self.manage_publish_profiles()
            return

        publisher_class = self.store_publishers.get(selected_store_enum)
        if not publisher_class:
            QMessageBox.critical(self, "Error", f"No publisher found for {selected_store_enum.value}")
            return

        try:
            self.validate_build_content()

            if selected_store_enum == StoreEnum.steam:
                publisher_instance = publisher_class(self.publish_profile)
                logging.info(f"Attempting to publish build '{self.build_id}' to Steam...")
            else:
                publisher_instance = publisher_class(self.publish_profile)
                logging.info(f"Attempting to publish build '{self.build_id}' to {selected_store_enum}...")

            publisher_instance.validate_publish_profile()

            preflight_result = validate_publish_preflight(
                build_root=self.build_root,
                publish_profile=self.publish_profile,
                selected_store=selected_store_enum,
            )
            preflight_dialog = PreflightDialog(preflight_result, parent=self)
            if preflight_dialog.exec() != QDialog.DialogCode.Accepted:
                return

            publisher_instance.publish(content_dir=self.build_root, version=self.build.version)

        except InvalidConfigurationError as e:
            QMessageBox.warning(self, "Publishing Error",
                                  f"Failed to publish '{self.build_id}' to {selected_store_enum.value}:\n\n{str(e)}")
        except NotImplementedError:
            QMessageBox.critical(self, "Not Implemented",
                                   f"Publishing for {selected_store_enum.value} is not yet implemented.")
        except Exception as e:
            logging.info(f"Error during publish execution: {e}")
            QMessageBox.critical(self, "Publishing Failed",
                                   f"An unexpected error occurred while publishing to {selected_store_enum.value}:\n\n{str(e)}")
