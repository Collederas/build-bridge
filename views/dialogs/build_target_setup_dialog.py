import os
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
    QWidget,
    QMessageBox,
)
from PyQt6.QtCore import Qt

from core.vcs.p4client import P4Client
from models import (
    BuildTarget,
    Project,
    BuildTargetPlatformEnum,
    BuildTypeEnum,
    VCSConfig,
    VCSTypeEnum,
)
from database import SessionFactory
from views.dialogs.settings_dialog import SettingsDialog


class BuildTargetSetupDialog(QDialog):

    def __init__(self, build_target_id: id = None):
        super().__init__()
        self.setWindowTitle("Build Target Setup")
        self.setMinimumSize(800, 500)

        # -- SESSION SETUP --
        # The Dialog owns the session here.
        # Session is managed at widget level (closed on dialog close, committed on accept)
        self.session = SessionFactory()

        if build_target_id:
            self.build_target = self.session.query(BuildTarget).get(build_target_id)
            self.session.add(self.build_target)
        else:
            self.build_target = None

        self.session_project = self.get_or_create_session_project(self.session)
        # -- END SESSION SETUP

        # -- VCS SETUP --
        if self.build_target and self.build_target.vcs_config:
            self.vcs_client = self.vcs_clients.get(
                self.build_target.vcs_config.vcs_type,
            )(self.build_target.vcs_config)
        else:
            self.vcs_client = None
        # Cached flag to determine versioning model (if vcs is connected, which we discover in initialize_form below)
        # then we can try to use tags/labels/streams for versioning.
        self.vcs_connected = False
        # -- END VCS SETUP

        self.stack = QStackedWidget()
        self.page1 = self.create_page1()
        self.page2 = self.create_page2()

        self.stack.addWidget(self.page1)
        self.stack.addWidget(self.page2)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.addLayout(self.add_header("Build Target"))
        self.main_layout.addWidget(self.stack)
        self.main_layout.addLayout(self.create_footer())

        self.initialize_form()

    def get_or_create_session_project(self, session):
        """
        Populate project data and create default if no project exists.
        Adds it to the given session.
        """
        # Get project from build target if we have one already and we
        # are just editing
        if self.build_target and self.build_target.project:
            session_project = self.build_target.project
        else:
            # See if there is one project in db
            session_project = session.query(Project).first()

            if not session_project:
                # If no project exists, we create a default (this is also done in settings)
                # so a project is created either there or here, depending on where user
                # gets first
                session_project = Project()
                session_project.name = "My Game"

        session.add(session_project)
        print(
            f"Added {session_project.name} - ID: {session_project.id} to the session."
        )
        return session_project

    def add_header(self, title_text):
        title_layout = QHBoxLayout()
        title = QLabel(title_text)
        title.setStyleSheet("font-weight: bold; font-size: 18px;")
        title_layout.addWidget(title)
        return title_layout

    def create_page1(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Page title
        page1_title = QLabel("Project")
        page1_title.setStyleSheet("font-weight: bold; font-size: 18px;")
        layout.addWidget(page1_title)

        # Project info
        project_form = QFormLayout()

        self.project_combo = QComboBox()

        self.source_edit = QLineEdit()
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_folder)

        source_layout = QHBoxLayout()
        source_layout.addWidget(self.source_edit)
        source_layout.addWidget(browse_button)

        project_form.addRow("Project:", self.project_combo)
        project_form.addRow("Project Source", source_layout)

        layout.addLayout(project_form)
        layout.addSpacing(20)

        # VCS Section (now below project section)
        vcs_title = QLabel("VCS")
        vcs_title.setStyleSheet("font-weight: bold;")
        vcs_desc = QLabel(
            "You can setup VCS to let BuildBridge switch automatically to "
            "target branch and try to look for tags to tag the release package."
        )
        vcs_desc.setWordWrap(True)
        vcs_desc.setStyleSheet("color: gray; font-size: 11px;")

        self.vcs_combo = QComboBox()
        vcs_type_layout = QHBoxLayout()
        vcs_type_layout.addWidget(QLabel("VCS Type:"))
        vcs_type_layout.addWidget(self.vcs_combo)

        vcs_settings_button = QPushButton("Setup VCS")
        vcs_settings_button.clicked.connect(self.open_vcs_settings)
        vcs_type_layout.addWidget(vcs_settings_button)

        self.branch_combo = QComboBox()
        branch_layout = QHBoxLayout()
        branch_layout.addWidget(QLabel("Target Branch:"))
        branch_layout.addWidget(self.branch_combo)

        # Add auto sync checkbox
        self.auto_sync_checkbox = QCheckBox("Automatically sync branch before build")
        self.auto_sync_hint = QLabel(
            "When enabled, will automatically sync/pull the target branch before building"
        )
        self.auto_sync_hint.setStyleSheet("color: gray; font-size: 10px;")
        self.auto_sync_hint.setWordWrap(True)

        auto_sync_layout = QVBoxLayout()
        auto_sync_layout.addWidget(self.auto_sync_checkbox)
        auto_sync_layout.addWidget(self.auto_sync_hint)

        layout.addWidget(vcs_title)
        layout.addWidget(vcs_desc)
        layout.addSpacing(10)
        layout.addLayout(vcs_type_layout)
        layout.addLayout(branch_layout)
        layout.addLayout(auto_sync_layout)  # Add the auto sync checkbox
        layout.addStretch()

        return widget

    def create_page2(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Title for Page 2
        page2_title = QLabel("Build Config")
        page2_title.setStyleSheet("font-weight: bold; font-size: 18px;")
        layout.addWidget(page2_title)

        form = QFormLayout()
        self.build_type_combo = QComboBox()
        self.target_platform_combo = QComboBox()

        self.optimize_checkbox = QCheckBox("Optimize Packaging for Steam")
        self.optimize_hint = QLabel(
            "Will build using Valve\nRecommended padding alignment values"
        )
        self.optimize_hint.setStyleSheet("color: gray; font-size: 10px;")
        self.optimize_hint.setWordWrap(True)

        optimize_layout = QVBoxLayout()
        optimize_layout.addWidget(self.optimize_checkbox)
        optimize_layout.addWidget(self.optimize_hint)

        form.addRow("Build Type", self.build_type_combo)
        form.addRow("Target Platform", self.target_platform_combo)
        form.addRow(optimize_layout)

        layout.addLayout(form)
        layout.addStretch()

        return widget

    def create_footer(self):
        self.footer_layout = QHBoxLayout()
        self.footer_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

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

        self.footer_layout.addStretch()
        self.footer_layout.addWidget(self.page1_label)
        self.footer_layout.addWidget(self.page2_label)
        self.footer_layout.addSpacing(20)
        self.footer_layout.addWidget(self.next_button)
        self.footer_layout.addWidget(self.save_button)

        return self.footer_layout

    def page1_clicked(self, event):
        """Switch to page 1 on label click"""
        self.stack.setCurrentIndex(0)
        self.page1_label.setStyleSheet(
            "background-color: black; color: white; padding: 4px 10px; border-radius: 10px;"
        )
        self.page2_label.setStyleSheet("color: gray; margin-left: 8px;")

        self.next_button.show()
        self.save_button.hide()

    def page2_clicked(self, event):
        """Switch to page 2 on label click"""
        self.stack.setCurrentIndex(1)
        self.page1_label.setStyleSheet("color: gray; margin-right: 8px;")
        self.page2_label.setStyleSheet(
            "background-color: black; color: white; padding: 4px 10px; border-radius: 10px;"
        )

        self.next_button.hide()
        self.save_button.show()

    def next_page(self):
        if self.stack.currentIndex() == 0:
            self.page2_clicked(None)  # Simulate click to page 2

    def browse_folder(self):
        start_dir = (
            self.source_edit.text() if os.path.isdir(self.source_edit.text()) else ""
        )

        folder = QFileDialog.getExistingDirectory(
            self, "Select Project Folder", start_dir
        )
        if folder:
            self.source_edit.setText(folder)

    def open_vcs_settings(self):
        settings_dialog = SettingsDialog(default_page=1)
        result = settings_dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            self.vc

    def initialize_form(self):
        """One-time initialization of all UI elements with their values"""

        # VCS Type
        self.vcs_combo.clear()
        self.vcs_combo.addItems([e.value.capitalize() for e in VCSTypeEnum])

        if self.build_target and self.build_target.vcs_config:
            current_vcs = (
                self.build_target.vcs_config.vcs_type.value.capitalize()
                if self.build_target
                else VCSTypeEnum.perforce.value.capitalize()
            )
            self.vcs_combo.setCurrentText(current_vcs)

        # VCS Branches

        # If we have a valid client (and is configured well)
        # add all branches to the combobox. And then set default if
        # we already have a build target configured in the db
        if self.vcs_client:
            branches = self.vcs_client.get_branches()

            if branches:
                self.vcs_connected = True
        else:
            branches = []
            self.vcs_connected = False

        self.branch_combo.clear()

        # Set default
        current_branch = self.build_target.target_branch if self.build_target else ""
        if current_branch:
            self.branch_combo.addItem(current_branch)
        self.branch_combo.setCurrentText(current_branch)

        # Auto sync branch
        self.auto_sync_checkbox.setChecked(
            bool(self.build_target.auto_sync_branch) if self.build_target else False
        )

        # Build Type
        self.build_type_combo.clear()
        self.build_type_combo.addItems([e.value for e in BuildTypeEnum])
        current_build = (
            self.build_target.build_type.value
            if self.build_target
            else BuildTypeEnum.prod.value
        )
        self.build_type_combo.setCurrentText(current_build)

        # Platform
        self.target_platform_combo.clear()
        platforms = [platform.value for platform in BuildTargetPlatformEnum]
        self.target_platform_combo.addItems(platforms)

        if self.build_target:
            current_platform = self.build_target.target_platform
            self.target_platform_combo.setCurrentText(current_platform)
        else:
            self.target_platform_combo.setCurrentIndex(0)

        # Extra build fields
        self.optimize_checkbox.setChecked(
            bool(self.build_target.optimize_for_steam) if self.build_target else True
        )

        # Project section
        projects = self.session.query(Project).all()

        for project in projects:
            self.project_combo.addItem(project.name)

        index = self.project_combo.findText(self.session_project.name)
        if index >= 0:  # If found
            self.project_combo.setCurrentIndex(index)

        # Set the default value of the source_dir field
        self.source_edit.setText(self.session_project.source_dir)

        # Add the session project to the session so it will be updated/saved when
        # user accepts dialog
        self.session.add(self.session_project)

    def accept(self):
        try:
            if not self.session_project:
                raise Exception(
                    "No session project! We need one to accept this dialog."
                )

            # Create a new BuildTarget if it doesn't exist
            if not self.build_target:
                self.build_target = BuildTarget()
                self.build_target.project = self.session_project
                self.session.add(self.build_target)

            # Map to an existing VCSConfig
            selected_vcs_type = VCSTypeEnum(self.vcs_combo.currentText().lower())
            existing_vcs_config = (
                self.session.query(VCSConfig)
                .filter_by(
                    vcs_type=selected_vcs_type, build_target_id=self.build_target.id
                )
                .first()
            )
            if existing_vcs_config:
                self.build_target.vcs_config = existing_vcs_config
            else:
                self.build_target.vcs_config = (
                    None  # Unlink if no matching config exists
                )

            # Update BuildTarget fields
            self.build_target.auto_sync_branch = self.auto_sync_checkbox.isChecked()
            self.build_target.target_branch = self.branch_combo.currentText()

            build_type_text = self.build_type_combo.currentText().lower()
            self.build_target.build_type = (
                BuildTypeEnum.dev
                if build_type_text == "development"
                else BuildTypeEnum.prod
            )

            platform_text = self.target_platform_combo.currentText()
            self.build_target.target_platform = BuildTargetPlatformEnum(platform_text)

            self.build_target.optimize_for_steam = self.optimize_checkbox.isChecked()
            self.build_target.project.source_dir = self.source_edit.text()

            # Commit to DB
            self.session.commit()

            print(
                f"BuildTarget {self.build_target.id} saved for project: {self.build_target.project.name}, target platform: {self.build_target.target_platform}"
            )
            super().accept()

        except Exception as e:
            self.reject()
            QMessageBox.critical(
                self, "Error", f"Failed to save configuration: {str(e)}"
            )
        finally:
            if self.vcs_client:
                self.vcs_client._disconnect()

    def reject(self):
        """User clicked Cancel - rollback any changes"""
        print("User canceled Build Target Setup. Discard settings.")
        try:
            self.session.rollback()
        except:
            pass  # Session might already be invalid
        finally:
            self.session.close()
            super().reject()

    def closeEvent(self, event):
        if self.vcs_client:
            self.vcs_client._disconnect()

        if self.session.dirty:  # Example: Check if there are uncommitted changes
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Close anyway?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.reject()  # Rollback and close
                event.accept()
            else:
                event.ignore()  # Keep the dialog open
        else:
            self.reject()  # No changes, just rollback and close
            event.accept()
