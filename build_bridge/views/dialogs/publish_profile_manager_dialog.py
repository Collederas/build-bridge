from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from build_bridge.models import (
    ItchPublishProfile,
    Project,
    PublishProfile,
    SteamPublishProfile,
    StoreEnum,
)
from build_bridge.views.dialogs.publish_profile_dialog import PublishProfileDialog

PROFILE_ID_ROLE = Qt.ItemDataRole.UserRole


class PublishProfileManagerDialog(QDialog):
    profile_selected_signal = pyqtSignal(object)
    profiles_changed_signal = pyqtSignal()

    profile_models = {
        StoreEnum.itch: ItchPublishProfile,
        StoreEnum.steam: SteamPublishProfile,
    }

    def __init__(
        self,
        session,
        build_id: str,
        store_type: StoreEnum,
        selected_profile_id: int | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.session = session
        self.build_id = build_id
        self.store_type = store_type
        self.selected_profile_id = selected_profile_id

        self.setWindowTitle(f"{store_type.value} Publish Profiles")
        self.setMinimumSize(560, 360)

        self._init_ui()
        self._refresh_profiles(selected_profile_id)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        header = QLabel(f"{self.store_type.value} profiles for {self.build_id}")
        header.setObjectName("sectionTitle")
        main_layout.addWidget(header)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)

        self.profile_list = QListWidget()
        self.profile_list.itemDoubleClicked.connect(lambda *_: self._edit_selected_profile())
        self.profile_list.currentItemChanged.connect(lambda *_: self._sync_button_state())
        content_layout.addWidget(self.profile_list, 1)

        button_layout = QVBoxLayout()
        self.new_button = QPushButton("New Profile")
        self.rename_button = QPushButton("Rename")
        self.edit_button = QPushButton("Edit")
        self.delete_button = QPushButton("Delete")
        self.use_button = QPushButton("Use Selected")
        self.use_button.setObjectName("primaryButton")

        self.new_button.clicked.connect(self._create_profile)
        self.rename_button.clicked.connect(self._rename_selected_profile)
        self.edit_button.clicked.connect(self._edit_selected_profile)
        self.delete_button.clicked.connect(self._delete_selected_profile)
        self.use_button.clicked.connect(self._use_selected_profile)

        button_layout.addWidget(self.new_button)
        button_layout.addWidget(self.rename_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.use_button)
        content_layout.addLayout(button_layout)

        main_layout.addLayout(content_layout, 1)

        footer_layout = QHBoxLayout()
        footer_layout.addStretch(1)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)
        footer_layout.addWidget(close_button)
        main_layout.addLayout(footer_layout)

    def _profile_model(self):
        return self.profile_models[self.store_type]

    def _profile_label(self, profile: PublishProfile):
        return (profile.description or "").strip() or f"Profile #{profile.id}"

    def _refresh_profiles(self, selected_profile_id=None):
        profiles = (
            self.session.query(self._profile_model())
            .filter_by(build_id=self.build_id)
            .order_by(PublishProfile.id.asc())
            .all()
        )

        self.profile_list.clear()
        for profile in profiles:
            item = QListWidgetItem(self._profile_label(profile))
            item.setData(PROFILE_ID_ROLE, profile.id)
            self.profile_list.addItem(item)

        if self.profile_list.count() == 0:
            empty_item = QListWidgetItem("No profiles yet")
            empty_item.setData(PROFILE_ID_ROLE, None)
            empty_item.setFlags(empty_item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.profile_list.addItem(empty_item)
        elif selected_profile_id is not None:
            for row in range(self.profile_list.count()):
                item = self.profile_list.item(row)
                if item.data(PROFILE_ID_ROLE) == selected_profile_id:
                    self.profile_list.setCurrentRow(row)
                    break
        else:
            self.profile_list.setCurrentRow(0)

        self._sync_button_state()

    def _selected_profile(self):
        current_item = self.profile_list.currentItem()
        if current_item is None:
            return None

        profile_id = current_item.data(PROFILE_ID_ROLE)
        if profile_id is None:
            return None

        return self.session.get(self._profile_model(), profile_id)

    def _make_profile_instance(self):
        project = self.session.query(Project).one_or_none()
        return self._profile_model()(
            project_id=project.id if project else None,
            build_id=self.build_id,
            store_type=self.store_type,
            description="New Profile",
        )

    def _open_editor(self, profile):
        dialog = PublishProfileDialog(
            session=self.session,
            publish_profile=profile,
            parent=self,
        )
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            profile_id = getattr(dialog.publish_profile, "id", None)
            self.profiles_changed_signal.emit()
            self._refresh_profiles(profile_id)

    def _create_profile(self):
        self._open_editor(self._make_profile_instance())

    def _edit_selected_profile(self):
        profile = self._selected_profile()
        if profile is not None:
            self._open_editor(profile)

    def _rename_selected_profile(self):
        profile = self._selected_profile()
        if profile is None:
            return

        current_name = self._profile_label(profile)
        new_name, accepted = QInputDialog.getText(
            self,
            "Rename Profile",
            "Profile name:",
            text=current_name,
        )
        if not accepted:
            return

        new_name = new_name.strip()
        if not new_name:
            QMessageBox.warning(
                self,
                "Rename Profile",
                "Profile name cannot be empty.",
            )
            return

        profile.description = new_name
        self.session.commit()
        self.selected_profile_id = profile.id
        self.profile_selected_signal.emit(profile)
        self.profiles_changed_signal.emit()
        self._refresh_profiles(profile.id)

    def _delete_selected_profile(self):
        profile = self._selected_profile()
        if profile is None:
            return

        response = QMessageBox.question(
            self,
            "Delete Profile",
            f"Delete publish profile '{self._profile_label(profile)}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return

        deleted_selected_profile = profile.id == self.selected_profile_id
        self.session.delete(profile)
        self.session.commit()
        if deleted_selected_profile:
            self.selected_profile_id = None
            self.profile_selected_signal.emit(None)
        self.profiles_changed_signal.emit()
        self._refresh_profiles()

    def _use_selected_profile(self):
        profile = self._selected_profile()
        if profile is None:
            return
        self.selected_profile_id = profile.id
        self.profile_selected_signal.emit(profile)
        self.accept()

    def _sync_button_state(self):
        has_profile = self._selected_profile() is not None
        self.rename_button.setEnabled(has_profile)
        self.edit_button.setEnabled(has_profile)
        self.delete_button.setEnabled(has_profile)
        self.use_button.setEnabled(has_profile)
