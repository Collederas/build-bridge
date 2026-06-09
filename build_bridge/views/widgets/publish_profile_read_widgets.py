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
from build_bridge.views.dialogs.publish_profile_dialog import PublishProfileDialog
from build_bridge.views.dialogs.publish_run_dialog import PublishRunDialog


class PublishProfileListWidget(QWidget):
    def __init__(self, project_id: int | None = None):
        super().__init__()
        self.session = SessionFactory()
        self._project_id = project_id

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

    def set_project_id(self, project_id: int | None):
        self._project_id = project_id
        self.refresh_builds()

    def _get_project(self):
        if self._project_id is None:
            return None
        return self.session.get(Project, self._project_id)

    def refresh_builds(self):
        """Re-queries the DB and rebuilds the builds list."""
        while self.vbox.count():
            child = self.vbox.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        try:
            self.session.expire_all()
            project = self._get_project()
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
        project = self._get_project()
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
    store_order = [StoreEnum.steam, StoreEnum.itch]

    def __init__(self, build: Build, session, show_target_name: bool = True, on_build_removed=None):
        super().__init__()
        self.build = build
        self.build_root = build.output_path
        self.build_id = build.version
        self.session = session
        self.on_build_removed = on_build_removed

        # Per-store widgets keyed by StoreEnum
        self.store_checkboxes: dict[StoreEnum, QCheckBox] = {}
        self.store_status_labels: dict[StoreEnum, QLabel] = {}
        self.store_configure_buttons: dict[StoreEnum, QPushButton] = {}

        self.setObjectName("buildRow")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 7, 10, 7)
        outer.setSpacing(6)

        # --- Top row: build info + actions ---
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

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

        display_name = (
            f"{target_name} - {build.version}" if (show_target_name and target_name) else build.version
        )

        self.display_name_label = QLabel(display_name)
        self.display_name_label.setObjectName("primaryText")
        self.display_name_label.setWordWrap(True)
        self.display_name_label.setFont(display_name_font)
        self.display_name_label.setToolTip(f"Build folder:\n{self.build_root}")
        build_info_layout.addWidget(self.display_name_label)

        self.profile_value_label = QLabel(self._get_build_status_label())
        self.profile_value_label.setObjectName("secondaryText")
        self.profile_value_label.setWordWrap(True)
        build_info_layout.addWidget(self.profile_value_label)
        top_row.addWidget(build_info, 1)

        browse_archive_button = QPushButton("Browse")
        browse_archive_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        browse_archive_button.setToolTip(f"Open build folder:\n{self.build_root}")
        browse_archive_button.clicked.connect(self.browse_archive_directory)
        browse_archive_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        top_row.addWidget(browse_archive_button)

        remove_button = QPushButton("Remove")
        remove_button.setObjectName("dangerButton")
        remove_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        remove_button.setToolTip("Remove this build from the list")
        remove_button.clicked.connect(self.handle_remove)
        remove_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        top_row.addWidget(remove_button)

        outer.addLayout(top_row)

        # --- Per-store selection row ---
        stores_row = QHBoxLayout()
        stores_row.setSpacing(14)

        for store in self.store_order:
            cell = QHBoxLayout()
            cell.setSpacing(4)

            checkbox = QCheckBox(store.value)
            checkbox.toggled.connect(self._refresh_publish_button)
            self.store_checkboxes[store] = checkbox
            cell.addWidget(checkbox)

            status = QLabel("…")
            status.setObjectName("storePreflightStatus")
            self.store_status_labels[store] = status
            cell.addWidget(status)

            configure = QPushButton("Configure")
            configure.setObjectName("ghostButton")
            configure.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            configure.clicked.connect(lambda _checked, s=store: self.manage_publish_profile(s))
            self.store_configure_buttons[store] = configure
            cell.addWidget(configure)

            stores_row.addLayout(cell)

        stores_row.addStretch(1)

        self.publish_button = QPushButton("Publish")
        self.publish_button.setObjectName("primaryButton")
        self.publish_button.clicked.connect(self.handle_publish)
        self.publish_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        stores_row.addWidget(self.publish_button)

        outer.addLayout(stores_row)

        self.refresh_store_statuses()

    # ------------------------------------------------------------------ data

    def _get_build_status_label(self):
        status = getattr(self.build.status, "value", self.build.status) or "unknown"
        created_at = getattr(self.build, "created_at", None)
        if created_at:
            return f"{status} | {created_at:%Y-%m-%d %H:%M}"
        return str(status)

    @property
    def _project_id(self):
        return self.build.build_target.project_id if self.build.build_target else None

    def _load_publish_profile(self, store: StoreEnum) -> PublishProfile | None:
        profile_model = self.profile_models[store]
        try:
            return (
                self.session.query(profile_model)
                .filter_by(project_id=self._project_id, store_type=store)
                .order_by(PublishProfile.id.asc())
                .first()
            )
        except Exception as e:
            logging.info(f"Error loading {store.value} profile: {e}")
            return None

    def _get_or_create_publish_profile(self, store: StoreEnum):
        existing = self._load_publish_profile(store)
        if existing is not None:
            return existing

        project = self.build.build_target.project if self.build.build_target else None
        profile_model = self.profile_models[store]
        return profile_model(
            project_id=self._project_id,
            store_type=store,
            description=(project.name if project else None) or "Default",
        )

    def _preflight_store(self, store: StoreEnum):
        """Return (profile, PreflightResult | None). Result is None when no profile exists."""
        profile = self._load_publish_profile(store)
        if profile is None:
            return None, None
        try:
            result = validate_publish_preflight(self.build_root, profile, store)
        except Exception as exc:
            logging.info(f"Preflight error for {store.value}: {exc}", exc_info=True)
            result = None
        return profile, result

    # ---------------------------------------------------------------- UI sync

    def refresh_store_statuses(self):
        for store in self.store_order:
            checkbox = self.store_checkboxes[store]
            status = self.store_status_labels[store]
            profile, result = self._preflight_store(store)

            if profile is None:
                severity = "none"
                status.setText("⚠ not configured")
                tip = "No publish profile has been created for this store yet."
                status.setToolTip(tip)
                checkbox.setEnabled(False)
                checkbox.setChecked(False)
                checkbox.setToolTip(tip)
            elif result is None:
                severity = "error"
                status.setText("✗ preflight failed")
                tip = "Could not run preflight checks (see logs)."
                status.setToolTip(tip)
                checkbox.setEnabled(False)
                checkbox.setChecked(False)
                checkbox.setToolTip(tip)
            elif result.has_blockers:
                severity = "error"
                status.setText("✗ issues")
                tip = self._format_issues(result, "error")
                status.setToolTip(tip)
                checkbox.setEnabled(False)
                checkbox.setChecked(False)
                checkbox.setToolTip(tip)
            elif result.has_warnings:
                severity = "warning"
                status.setText("⚠ warnings")
                tip = self._format_issues(result, "warning")
                status.setToolTip(tip)
                checkbox.setEnabled(True)
                checkbox.setToolTip(f"Publish this build to {store.value}.\n\n{tip}")
            else:
                severity = "ok"
                status.setText("✓ ready")
                status.setToolTip("")
                checkbox.setEnabled(True)
                checkbox.setToolTip(f"Publish this build to {store.value}.")

            status.setProperty("severity", severity)
            status.style().unpolish(status)
            status.style().polish(status)

        self._refresh_publish_button()

    @staticmethod
    def _format_issues(result, severity: str) -> str:
        lines = []
        for issue in result.issues:
            if issue.severity != severity:
                continue
            if issue.detail:
                lines.append(f"• {issue.label}: {issue.detail}")
            else:
                lines.append(f"• {issue.label}")
        return "\n".join(lines)

    def _refresh_publish_button(self):
        selected = [s for s, cb in self.store_checkboxes.items() if cb.isChecked()]
        self.publish_button.setEnabled(bool(selected))
        if selected:
            labels = ", ".join(s.value for s in selected)
            self.publish_button.setToolTip(f"Publish build '{self.build_id}' to: {labels}")
        else:
            self.publish_button.setToolTip("Select at least one configured store to publish.")

    # ------------------------------------------------------------- configure

    def manage_publish_profile(self, store: StoreEnum):
        profile = self._get_or_create_publish_profile(store)
        dialog = PublishProfileDialog(
            session=self.session,
            publish_profile=profile,
            parent=self,
        )
        dialog.exec()
        self.refresh_store_statuses()

    # ------------------------------------------------------------- publishing

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

    def handle_publish(self):
        selected_stores = [s for s, cb in self.store_checkboxes.items() if cb.isChecked()]
        if not selected_stores:
            return

        try:
            self.validate_build_content()
        except InvalidConfigurationError as exc:
            QMessageBox.warning(self, "Publishing Error", str(exc))
            return

        # Resolve profiles for selected stores; abort if any selected store is unconfigured
        # or has blocking preflight issues. Warnings proceed silently.
        profiles_by_store: dict[StoreEnum, PublishProfile] = {}
        blockers_by_store: dict[StoreEnum, str] = {}
        for store in selected_stores:
            profile, result = self._preflight_store(store)
            if profile is None:
                QMessageBox.warning(
                    self,
                    "Publishing Error",
                    f"{store.value} publishing is not configured for this project.",
                )
                return
            if result is not None and result.has_blockers:
                blockers_by_store[store] = self._format_issues(result, "error")
                continue
            profiles_by_store[store] = profile

        if blockers_by_store:
            sections = [
                f"[{store.value}]\n{detail}" for store, detail in blockers_by_store.items()
            ]
            QMessageBox.warning(
                self,
                "Publishing Error",
                "Fix the following before publishing:\n\n" + "\n\n".join(sections),
            )
            return

        # Build specs after preflight passes.
        specs = []
        for store, profile in profiles_by_store.items():
            publisher = self.store_publishers[store](profile)
            try:
                specs.append(publisher.prepare(content_dir=self.build_root, version=self.build.version))
            except InvalidConfigurationError as exc:
                QMessageBox.warning(
                    self,
                    "Publishing Error",
                    f"Failed to prepare {store.value} publish:\n\n{exc}",
                )
                return
            except Exception as exc:
                logging.info(f"Unexpected error preparing {store.value}: {exc}", exc_info=True)
                QMessageBox.critical(
                    self,
                    "Publishing Error",
                    f"Unexpected error preparing {store.value}:\n\n{exc}",
                )
                return

        title = f"Publishing {self.build.build_target.name if self.build.build_target else ''} - {self.build_id}"
        run_dialog = PublishRunDialog(specs, title=title)

        # Register with main window so close-app prompt knows about it.
        main_window = self.window()
        register = getattr(main_window, "register_run_dialog", None)
        if callable(register):
            register(run_dialog)

        run_dialog.show()
        run_dialog.raise_()
        run_dialog.activateWindow()

    # ----------------------------------------------------------------- misc

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
            QMessageBox.critical(self, "Remove Build", f"Build was not removed.\n\n{e}")
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
