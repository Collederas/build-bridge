import os, logging
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox,
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
from sqlalchemy.orm import selectinload

from build_bridge.models import (
    Build,
    BuildStatusEnum,
    BuildTarget,
    ItchPublishProfile,
    Project,
    PublishProfile,
    SteamPublishProfile,
    StoreEnum,
)
from build_bridge.core.builds import BuildDeletionError, delete_build
from build_bridge.core.publisher.itch.itch_publisher import ItchPublisher
from build_bridge.core.preflight import validate_publish_preflight
from build_bridge.database import SessionFactory
from build_bridge.exceptions import InvalidConfigurationError
from build_bridge.core.publisher.steam.steam_publisher import SteamPublisher
from build_bridge.views.dialogs.preflight_dialog import PreflightDialog
from build_bridge.views.dialogs.publish_profile_dialog import PublishProfileDialog


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

        self.import_button = QPushButton("Import from disk")
        self.import_button.setObjectName("ghostButton")
        self.import_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        )
        self.import_button.setToolTip("Scan archive directory for existing build folders and import them")
        self.import_button.clicked.connect(self._import_from_disk)
        self.import_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        toolbar_layout.addWidget(self.import_button)

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
        self.vbox.setSpacing(14)
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

            build_targets = (
                self.session.query(BuildTarget)
                .options(selectinload(BuildTarget.builds))
                .filter(BuildTarget.project_id == project.id)
                .order_by(BuildTarget.id.asc())
                .all()
            )
            build_groups = []
            for build_target in build_targets:
                builds = sorted(
                    build_target.builds,
                    key=lambda build: build.created_at,
                    reverse=True,
                )
                if builds:
                    build_groups.append((build_target, builds))

        except Exception as e:
            logging.info(f"Error querying builds: {e}", exc_info=True)
            self.empty_message_label.setText("Error loading builds.")
            self.empty_message_label.setVisible(True)
            self.scroll_area.setVisible(False)
            return

        if not build_groups:
            self.empty_message_label.setText("No builds available.")
            self.empty_message_label.setVisible(True)
            self.scroll_area.setVisible(False)
            return

        self.scroll_area.setVisible(True)
        self.empty_message_label.setVisible(False)

        for build_target, builds in build_groups:
            group_widget = BuildTargetBuildGroup(
                build_target=build_target,
                builds=builds,
                session=self.session,
                on_build_removed=self.refresh_builds,
            )
            self.vbox.addWidget(group_widget)

        self.vbox.addStretch(1)

    def _import_from_disk(self):
        """Scan archive_dir/project_name/ for version folders not yet in the DB."""
        self.session.expire_all()
        project = self.session.query(Project).first()
        if not project or not project.archive_directory:
            QMessageBox.warning(self, "Import", "No project configured.")
            return

        targets = (
            self.session.query(BuildTarget)
            .filter_by(project_id=project.id)
            .order_by(BuildTarget.id)
            .all()
        )
        if not targets:
            QMessageBox.warning(self, "Import", "No build targets found. Add a build target first.")
            return

        # Scan archive_dir/project_name/ — subdirs that are NOT target names are
        # old-style version folders (pre-refactor builds).
        scan_root = Path(project.archive_directory) / project.name
        if not scan_root.exists():
            QMessageBox.information(self, "Import", f"Directory not found:\n{scan_root}")
            return

        target_names = {t.name for t in targets if t.name}
        existing_paths = {b.output_path for b in self.session.query(Build.output_path).all()}

        imported = 0
        for entry in sorted(scan_root.iterdir()):
            if not entry.is_dir() or entry.name in target_names:
                continue
            version = entry.name
            output_path = str(entry)
            if output_path in existing_paths:
                continue

            # Assign to the first (or only) build target; ambiguity is rare in
            # the single-project model this app uses.
            build = Build(
                build_target_id=targets[0].id,
                version=version,
                output_path=output_path,
                status=BuildStatusEnum.success,
                created_at=datetime.fromtimestamp(entry.stat().st_mtime),
            )
            self.session.add(build)
            imported += 1

        self.session.commit()

        if imported:
            QMessageBox.information(self, "Import", f"Imported {imported} build(s).")
            self.refresh_builds()
        else:
            QMessageBox.information(self, "Import", "No new builds found to import.")

    def closeEvent(self, a0):
        self.session.close()
        return super().closeEvent(a0)


class BuildTargetBuildGroup(QWidget):
    def __init__(self, build_target: BuildTarget, builds: list[Build], session, on_build_removed=None):
        super().__init__()
        self.setObjectName("buildTargetGroup")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("buildTargetGroupHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 5, 10, 5)
        header_layout.setSpacing(8)

        target_label = QLabel(f"Build target: {repr(build_target)}")
        target_label.setObjectName("groupTitle")
        target_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        target_label.setWordWrap(True)
        header_layout.addWidget(target_label, 1)

        count_label = QLabel(f"{len(builds)} build{'s' if len(builds) != 1 else ''}")
        count_label.setObjectName("groupMeta")
        header_layout.addWidget(count_label)

        layout.addWidget(header)

        builds_body = QWidget()
        builds_body.setObjectName("buildTargetBuildList")
        builds_layout = QVBoxLayout(builds_body)
        builds_layout.setContentsMargins(10, 0, 0, 0)
        builds_layout.setSpacing(0)

        for build in builds:
            builds_layout.addWidget(
                PublishProfileEntry(
                    build=build,
                    session=session,
                    show_target_name=False,
                    on_build_removed=on_build_removed,
                )
            )

        layout.addWidget(builds_body)


class PublishProfileEntry(QWidget):
    store_publishers = {StoreEnum.itch: ItchPublisher, StoreEnum.steam: SteamPublisher}
    profile_models = {
        StoreEnum.itch: ItchPublishProfile,
        StoreEnum.steam: SteamPublishProfile,
    }

    def __init__(self, build: Build, session, show_target_name: bool = True, on_build_removed=None):
        super().__init__()
        self.build = build
        self.build_root = build.output_path
        self.build_id = build.version  # kept for compatibility with existing label references
        self.publish_profile: PublishProfile | None = None
        self.session = session
        self.on_build_removed = on_build_removed

        self.setObjectName("buildRow")
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(10, 7, 10, 7)
        self.main_layout.setSpacing(10)

        build_info = QWidget()
        build_info_layout = QVBoxLayout(build_info)
        build_info_layout.setContentsMargins(0, 0, 0, 0)
        build_info_layout.setSpacing(2)
        build_info.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        display_name_font = QFont()
        display_name_font.setBold(True)

        target_name = ""
        try:
            target_name = build.build_target.name if build.build_target else ""
        except Exception:
            pass

        if show_target_name and target_name:
            display_name = f"{target_name} - {build.version}"
        else:
            display_name = build.version

        self.display_name_label = QLabel(display_name)
        self.display_name_label.setObjectName("primaryText")
        self.display_name_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.display_name_label.setWordWrap(True)
        self.display_name_label.setFont(display_name_font)
        self.display_name_label.setToolTip(f"Build folder:\n{self.build_root}")
        build_info_layout.addWidget(self.display_name_label)

        self.profile_value_label = QLabel("Publishing not configured")
        self.profile_value_label.setObjectName("secondaryText")
        self.profile_value_label.setWordWrap(True)
        build_info_layout.addWidget(self.profile_value_label)
        self.main_layout.addWidget(build_info, 1)

        self.store_type_combo = QComboBox()
        self.store_type_combo.setMinimumWidth(100)
        self.store_type_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        for store_enum in self.store_publishers.keys():
            self.store_type_combo.addItem(str(store_enum.value), store_enum)
        self.store_type_combo.setToolTip("Select the target platform for publishing this build")
        self.main_layout.addWidget(self.store_type_combo)

        self.manage_profiles_button = QPushButton("Configure...")
        self.manage_profiles_button.setObjectName("ghostButton")
        self.manage_profiles_button.setToolTip("Configure publishing for this build target and store")
        self.manage_profiles_button.clicked.connect(self.manage_publish_profiles)
        self.manage_profiles_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.main_layout.addWidget(self.manage_profiles_button)

        browse_archive_button = QPushButton("Browse")
        browse_archive_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        browse_archive_button.setToolTip(f"Open build folder:\n{self.build_root}")
        browse_archive_button.clicked.connect(self.browse_archive_directory)
        browse_archive_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.main_layout.addWidget(browse_archive_button)

        remove_button = QPushButton("Remove")
        remove_button.setObjectName("dangerButton")
        remove_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        remove_button.setToolTip("Remove this build from the list")
        remove_button.clicked.connect(self.handle_remove)
        remove_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.main_layout.addWidget(remove_button)

        self.publish_button = QPushButton("Publish")
        self.publish_button.setObjectName("primaryButton")
        self.publish_button.clicked.connect(self.handle_publish)
        self.publish_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.main_layout.addWidget(self.publish_button)

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
        self._load_default_publish_profile()
        self.update_publish_button_enabled()

    def _get_profile_label(self, profile: PublishProfile):
        store_label = getattr(profile.store_type, "value", "Store")
        return f"{store_label} configured"

    def _load_default_publish_profile(self):
        selected_store_enum = self.store_type_combo.currentData()
        if selected_store_enum is None:
            self.publish_profile = None
            self._refresh_profile_summary()
            return

        try:
            self.session.refresh(self.build)
            profile_model = self.profile_models[selected_store_enum]
            self.publish_profile = (
                self.session.query(profile_model)
                .filter_by(
                    build_target_id=self.build.build_target_id,
                    store_type=selected_store_enum,
                )
                .order_by(PublishProfile.id.asc())
                .first()
            )
        except Exception as e:
            logging.info(f"Error loading publishing configuration: {e}")
            self.publish_profile = None

        self._refresh_profile_summary()

    def _refresh_profile_summary(self):
        status_label = self._get_build_status_label()
        if self.publish_profile is None:
            selected_store_enum = self.store_type_combo.currentData()
            store_label = selected_store_enum.value if selected_store_enum else "store"
            self.profile_value_label.setText(f"{status_label} | {store_label} publishing not configured")
            self.profile_value_label.setToolTip("Use Configure... to set up publishing for this target.")
        else:
            profile_label = self._get_profile_label(self.publish_profile)
            self.profile_value_label.setText(f"{status_label} | {profile_label}")
            self.profile_value_label.setToolTip("Publishing is configured for this target and store.")

    def _get_build_status_label(self):
        status = getattr(self.build.status, "value", self.build.status) or "unknown"
        created_at = getattr(self.build, "created_at", None)
        if created_at:
            return f"{status} | {created_at:%Y-%m-%d %H:%M}"
        return str(status)

    def manage_publish_profiles(self):
        selected_platform_enum = self.store_type_combo.currentData()
        if selected_platform_enum is None:
            QMessageBox.information(self, "Select Store", "Please select a store before configuring publishing.")
            return

        profile = self._get_or_create_publish_profile(selected_platform_enum)
        dialog = PublishProfileDialog(
            session=self.session,
            publish_profile=profile,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.publish_profile = dialog.publish_profile

        self._load_default_publish_profile()
        self.update_publish_button_enabled()

    def _get_or_create_publish_profile(self, store_type: StoreEnum):
        profile_model = self.profile_models[store_type]
        profile = (
            self.session.query(profile_model)
            .filter_by(build_target_id=self.build.build_target_id, store_type=store_type)
            .order_by(PublishProfile.id.asc())
            .first()
        )
        if profile is not None:
            return profile

        target_name = ""
        if self.build.build_target and self.build.build_target.name:
            target_name = self.build.build_target.name

        return profile_model(
            build_target_id=self.build.build_target_id,
            store_type=store_type,
            description=target_name or "Default",
        )

    def _refresh_publish_tooltip(self):
        selected_platform_enum = self.store_type_combo.currentData()
        if self.publish_profile is None:
            store_label = selected_platform_enum.value if selected_platform_enum else "store"
            self.publish_button.setToolTip(f"Configure {store_label} publishing for this build target first.")
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

    def handle_remove(self):
        delete_from_disk = self._confirm_remove()
        if delete_from_disk is None:
            return

        try:
            delete_build(
                session=self.session,
                build=self.build,
                delete_from_disk=delete_from_disk,
            )
        except BuildDeletionError as e:
            QMessageBox.critical(
                self,
                "Remove Build",
                f"Build was not removed.\n\n{e}",
            )
            return
        except Exception as e:
            self.session.rollback()
            logging.info(f"Error removing build '{self.build_id}': {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Remove Build",
                f"An unexpected error occurred while removing this build:\n\n{e}",
            )
            return

        if self.on_build_removed:
            self.on_build_removed()

    def _confirm_remove(self) -> bool | None:
        build_path = Path(self.build_root).expanduser().resolve() if self.build_root else None
        folder_exists = bool(build_path and build_path.is_dir())

        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Icon.Warning)
        message_box.setWindowTitle("Remove Build")
        message_box.setText(f"Remove build '{self.build_id}' from Build Bridge?")
        if folder_exists:
            message_box.setInformativeText(
                "The build folder will stay on disk unless you choose to delete it."
            )
            message_box.setDetailedText(str(build_path))
            disk_checkbox = QCheckBox("Also delete the build folder from disk")
            message_box.setCheckBox(disk_checkbox)
        else:
            message_box.setInformativeText(
                "The build folder was not found on disk, so only the list entry will be removed."
            )
            disk_checkbox = None

        remove_button = message_box.addButton("Remove", QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = message_box.addButton(QMessageBox.StandardButton.Cancel)
        message_box.setDefaultButton(cancel_button)
        message_box.exec()

        if message_box.clickedButton() != remove_button:
            return None

        return bool(disk_checkbox and disk_checkbox.isChecked())

    def handle_publish(self):
        selected_store_enum = self.store_type_combo.currentData()
        if selected_store_enum is None:
            QMessageBox.warning(self, "Error", "No target platform selected.")
            return
        if self.publish_profile is None:
            QMessageBox.information(self, "Configure Publishing",
                                     "Configure publishing for this build target before publishing.")
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
