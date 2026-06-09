import logging

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QCheckBox,
    QMessageBox,
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import pyqtSignal
from sqlalchemy.exc import IntegrityError

from build_bridge.utils.paths import get_resource_path
from build_bridge.core.projects import get_active_project
from build_bridge.models import (
    BuildTarget,
    Project,
    BuildTargetPlatformEnum,
    BuildTypeEnum,
)
from build_bridge.database import SessionFactory


class BuildTargetSetupDialog(QDialog):
    """Single-page editor for a build target (a build *recipe*: name, platform,
    build type, Steam packaging). The project is fixed context, not an input —
    engine path, source and the .Target.cs are project-level (see Settings)."""

    build_target_created = pyqtSignal(int)

    def __init__(self, build_target_id: int = None, project_id: int | None = None):
        super().__init__()
        self.setWindowTitle("Build Target")
        self.setMinimumWidth(440)
        icon_path = str(get_resource_path("build_bridge/icons/buildbridge.ico"))
        self.setWindowIcon(QIcon(icon_path))

        self.session = SessionFactory()
        self.build_target = (
            self.session.get(BuildTarget, build_target_id) if build_target_id else None
        )
        self.session_project = self._resolve_project(project_id)

        self._build_ui()
        self._populate()

    def _resolve_project(self, project_id):
        """The project is determined by context: the target being edited, the id
        passed by the caller, or the active project — never chosen here."""
        if self.build_target and self.build_target.project:
            return self.session.merge(self.build_target.project)
        if project_id:
            return self.session.get(Project, project_id)
        return get_active_project(self.session)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel("Build Target")
        header.setStyleSheet("font-weight: bold; font-size: 18px;")
        layout.addWidget(header)

        project_name = self.session_project.name if self.session_project else "—"
        project_label = QLabel(project_name)
        project_label.setStyleSheet("color: gray;")

        form = QFormLayout()
        form.addRow("Project:", project_label)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Optional label, e.g. Main, Demo, QA")
        form.addRow("Name:", self.name_edit)

        self.build_type_combo = QComboBox()
        self.build_type_combo.addItems([e.value for e in BuildTypeEnum])
        form.addRow("Build Type:", self.build_type_combo)

        self.target_platform_combo = QComboBox()
        self.target_platform_combo.addItems([p.value for p in BuildTargetPlatformEnum])
        form.addRow("Target Platform:", self.target_platform_combo)

        self.optimize_checkbox = QCheckBox("Optimize packaging for Steam")
        self.optimize_checkbox.setToolTip(
            "Build using Valve's recommended pak padding alignment values."
        )
        form.addRow("Packaging:", self.optimize_checkbox)

        layout.addLayout(form)

        footer = QHBoxLayout()
        footer.addStretch()
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("primaryButton")
        self.save_button.clicked.connect(self.accept)
        footer.addWidget(cancel_button)
        footer.addWidget(self.save_button)
        layout.addLayout(footer)

    def _populate(self):
        bt = self.build_target
        self.name_edit.setText(bt.name if bt and bt.name else "")
        self.build_type_combo.setCurrentText(
            bt.build_type.value if bt and bt.build_type else BuildTypeEnum.prod.value
        )
        self.target_platform_combo.setCurrentText(
            bt.target_platform.value
            if bt and bt.target_platform
            else BuildTargetPlatformEnum.win_64.value
        )
        self.optimize_checkbox.setChecked(bool(bt.optimize_for_steam) if bt else True)

    def accept(self):
        if not self.session_project:
            QMessageBox.critical(
                self, "Error", "No project is associated with this build target."
            )
            return
        try:
            if not self.build_target:
                self.build_target = BuildTarget(project=self.session_project)
                self.session.add(self.build_target)

            self.build_target.name = self.name_edit.text().strip()
            self.build_target.build_type = BuildTypeEnum(self.build_type_combo.currentText())
            self.build_target.target_platform = BuildTargetPlatformEnum(
                self.target_platform_combo.currentText()
            )
            self.build_target.optimize_for_steam = self.optimize_checkbox.isChecked()

            self.session.commit()
            logging.info(
                f"BuildTarget {self.build_target.id} saved - "
                f"'{self.session_project.name}' / {self.build_target.target_platform.value} / "
                f"{self.build_target.build_type.value}."
            )
            self.build_target_created.emit(self.build_target.id)
            super().accept()

        except IntegrityError:
            self.session.rollback()
            QMessageBox.warning(
                self,
                "Duplicate Build Target",
                "A build target with this name, platform and build type already "
                "exists for this project. Change one of them to make it unique.",
            )
        except Exception as e:
            self.session.rollback()
            logging.info(f"Save failed: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to save:\n{str(e)}")

    def reject(self):
        self.session.rollback()
        self.session.close()
        super().reject()

    def closeEvent(self, event):
        is_dirty = False
        try:
            if self.session.is_active:
                is_dirty = bool(self.session.dirty or self.session.new or self.session.deleted)
        except Exception:
            pass

        if is_dirty:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Close anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self.reject()
        event.accept()
