import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QFileDialog, QCheckBox, QStackedWidget, QMessageBox, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from core.vcs.p4client import P4Client
from models import (
    BuildTarget, PerforceConfig, Project, BuildTargetPlatformEnum,
    BuildTypeEnum, VCSTypeEnum
)
from database import SessionFactory


class BuildTargetSetupDialog(QDialog):
    vcs_clients = {VCSTypeEnum.perforce: P4Client}
    build_target_created = pyqtSignal(int)

    def __init__(self, build_target_id: int = None):
        super().__init__()
        self.setWindowTitle("Build Target Setup")
        self.setMinimumSize(800, 500)

        self.session = SessionFactory()
        if build_target_id:
            self.build_target = self.session.query(BuildTarget).get(build_target_id)
            self.session.add(self.build_target)
        else:
            self.build_target = None

        self.session_project = self.get_or_create_session_project(self.session)
        self.vcs_client = None
        self.vcs_connected = False

        self.stack = QStackedWidget()
        self.page1 = self.create_page1()
        self.page2 = self.create_page2()

        self.stack.addWidget(self.page1)
        self.stack.addWidget(self.page2)

        self.main_layout = QVBoxLayout()
        self.main_layout.addLayout(self.add_header("Build Target"))
        self.main_layout.addWidget(self.stack)
        self.main_layout.addLayout(self.create_footer())
        self.setLayout(self.main_layout)

        self.initialize_form()

    def get_or_create_session_project(self, session):
        if self.build_target and self.build_target.project:
            session_project = self.build_target.project
        else:
            session_project = session.query(Project).first()
            if not session_project:
                session_project = Project(name="My Game")
        session.add(session_project)
        print(f"Added {session_project.name} - ID: {session_project.id} to the session.")
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

        # Project section
        proj_label =  QLabel("Project")
        proj_label.setStyleSheet("font-weight: bold; font-size: 18px;")
        layout.addWidget(proj_label)

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

        # VCS Section
        vcs_title = QLabel("VCS")
        vcs_title.setStyleSheet("font-weight: bold;")
        vcs_desc = QLabel("Configure VCS to enable branch switching and tagging for releases.")
        vcs_desc.setWordWrap(True)
        vcs_desc.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(vcs_title)
        layout.addWidget(vcs_desc)
        layout.addSpacing(10)

        # VCS Type (Perforce only)
        self.vcs_combo = QComboBox()
        vcs_type_layout = QHBoxLayout()
        vcs_type_layout.addWidget(QLabel("VCS Type:"))
        vcs_type_layout.addWidget(self.vcs_combo)
        layout.addLayout(vcs_type_layout)

        # Perforce Config (no stack needed)
        self.perforce_config_widget = self.create_perforce_config_widget()
        layout.addWidget(self.perforce_config_widget)

        # Test Connection Button
        self.test_connection_button = QPushButton("Test Connection")
        self.test_connection_button.clicked.connect(self.test_connection)
        layout.addWidget(self.test_connection_button)

        self.connection_status_label = QLabel("")
        self.connection_status_label.setWordWrap(True)
        self.connection_status_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.connection_status_label)

        # Branch and Auto-sync
        self.branch_combo = QComboBox()
        branch_layout = QHBoxLayout()
        branch_layout.addWidget(QLabel("Target Branch:"))
        branch_layout.addWidget(self.branch_combo)
        layout.addLayout(branch_layout)

        self.auto_sync_checkbox = QCheckBox("Automatically sync branch before build")
        self.auto_sync_hint = QLabel("When enabled, will automatically sync/pull the target branch before building")
        self.auto_sync_hint.setStyleSheet("color: gray; font-size: 10px;")
        self.auto_sync_hint.setWordWrap(True)
        auto_sync_layout = QVBoxLayout()
        auto_sync_layout.addWidget(self.auto_sync_checkbox)
        auto_sync_layout.addWidget(self.auto_sync_hint)
        layout.addLayout(auto_sync_layout)

        layout.addStretch()
        return widget

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
        self.optimize_hint = QLabel("Will build using Valve\nRecommended padding alignment values")
        self.optimize_hint.setStyleSheet("color: gray; font-size: 10px;")
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
        footer_layout = QHBoxLayout()
        footer_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.page1_label = QLabel("1")
        self.page1_label.setStyleSheet("background-color: black; color: white; padding: 4px 10px; border-radius: 10px;")
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
        self.page1_label.setStyleSheet("background-color: black; color: white; padding: 4px 10px; border-radius: 10px;")
        self.page2_label.setStyleSheet("color: gray; margin-left: 8px;")
        self.next_button.show()
        self.save_button.hide()

    def page2_clicked(self, event):
        self.stack.setCurrentIndex(1)
        self.page1_label.setStyleSheet("color: gray; margin-right: 8px;")
        self.page2_label.setStyleSheet("background-color: black; color: white; padding: 4px 10px; border-radius: 10px;")
        self.next_button.hide()
        self.save_button.show()

    def next_page(self):
        if self.stack.currentIndex() == 0:
            self.page2_clicked(None)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Project Folder", self.source_edit.text() or "")
        if folder:
            self.source_edit.setText(folder)

    def display_connection_status(self, message, color):
        self.connection_status_label.setText(message)
        self.connection_status_label.setStyleSheet(f"font-size: 12px; color: {color.name()};")

    def test_connection(self):
        vcs_type = VCSTypeEnum(self.vcs_combo.currentText().lower())
        vcs_client_class = self.vcs_clients.get(vcs_type)

        if not vcs_client_class:
            self.display_connection_status(f"Unsupported VCS type: {vcs_type.value}", QColor("red"))
            return

        try:
            config = PerforceConfig(
                user=self.p4_user_edit.text().strip(),
                server_address=self.p4_server_edit.text().strip(),
                client=self.p4_client_edit.text().strip()
            )
            config.p4password = self.p4_password_edit.text().strip()
            client = vcs_client_class(config)
            client.ensure_connected()
            self.display_connection_status("Connection successful", QColor("green"))
            self.on_vcs_changed()
        except Exception as e:
            self.on_vcs_changed()
            self.display_connection_status(f"Connection failed: {str(e)}", QColor("red"))

    def on_vcs_changed(self):
        vcs_type = VCSTypeEnum(self.vcs_combo.currentText().lower())
        self.branch_combo.clear()
        self.branch_combo.setEnabled(False)

        if vcs_client_class := self.vcs_clients.get(vcs_type):
            try:
                config = PerforceConfig(
                    user=self.p4_user_edit.text(),
                    server_address=self.p4_server_edit.text(),
                    client=self.p4_client_edit.text()
                )
                config.p4password = self.p4_password_edit.text()
                self.vcs_client = vcs_client_class(config)
                self.vcs_connected = True
                branches = self.vcs_client.get_branches() or []
                if branches:
                    self.branch_combo.addItems(branches)
                    self.branch_combo.setEnabled(True)
                    default_branch = self.build_target.target_branch if self.build_target else branches[0]
                    self.branch_combo.setCurrentText(default_branch)
                    print(f"Branches loaded: {branches}")
                else:
                    print(f"No branches found for {vcs_type}")
            except (ConnectionError, RuntimeError) as e:
                self.vcs_client = None
                self.vcs_connected = False
                print(f"VCS connection failed: {e}")
        else:
            self.vcs_client = None
            self.vcs_connected = False
            print(f"Unsupported VCS type: {vcs_type}")

    def initialize_form(self):
        self.vcs_combo.clear()
        self.vcs_combo.addItems(["Perforce"])  # Only Perforce supported
        self.vcs_combo.currentTextChanged.connect(self.on_vcs_changed)
        if self.build_target and self.build_target.vcs_config:
            self.vcs_combo.setCurrentText("Perforce")  # Only option

        if self.build_target and self.build_target.vcs_config:
            p4conf = self.build_target.vcs_config
            self.p4_user_edit.setText(p4conf.user)
            self.p4_server_edit.setText(p4conf.server_address)
            self.p4_client_edit.setText(p4conf.client)
            self.p4_password_edit.setText(p4conf.p4password or "")

        self.on_vcs_changed()

        self.auto_sync_checkbox.setChecked(
            bool(self.build_target.auto_sync_branch) if self.build_target else False
        )

        self.build_type_combo.clear()
        self.build_type_combo.addItems([e.value for e in BuildTypeEnum])
        current_build = self.build_target.build_type.value if self.build_target else BuildTypeEnum.prod.value
        self.build_type_combo.setCurrentText(current_build)

        self.target_platform_combo.clear()
        self.target_platform_combo.addItems([p.value for p in BuildTargetPlatformEnum])
        current_platform = self.build_target.target_platform if self.build_target else BuildTargetPlatformEnum.win_64.value
        self.target_platform_combo.setCurrentText(current_platform)

        self.optimize_checkbox.setChecked(
            bool(self.build_target.optimize_for_steam) if self.build_target else True
        )

        projects = self.session.query(Project).all()
        self.project_combo.clear()
        self.project_combo.addItems([p.name for p in projects])
        index = self.project_combo.findText(self.session_project.name)
        if index >= 0:
            self.project_combo.setCurrentIndex(index)
        self.source_edit.setText(self.session_project.source_dir)

    def accept(self):
        try:
            if not self.session_project:
                raise Exception("No session project available!")

            if not self.build_target:
                self.build_target = BuildTarget(project=self.session_project)
                self.session.add(self.build_target)

            vcs_type = VCSTypeEnum(self.vcs_combo.currentText().lower())
            vcs_config = self.build_target.vcs_config or PerforceConfig()
            vcs_config.user = self.p4_user_edit.text()
            vcs_config.server_address = self.p4_server_edit.text()
            vcs_config.client = self.p4_client_edit.text()
            vcs_config.p4password = self.p4_password_edit.text()
            vcs_config.vcs_type = vcs_type
            self.build_target.vcs_config = vcs_config
            self.session.add(vcs_config)

            self.build_target.auto_sync_branch = self.auto_sync_checkbox.isChecked()
            self.build_target.target_branch = self.branch_combo.currentText()
            self.build_target.build_type = BuildTypeEnum(self.build_type_combo.currentText().capitalize())
            self.build_target.target_platform = BuildTargetPlatformEnum(self.target_platform_combo.currentText())
            self.build_target.optimize_for_steam = self.optimize_checkbox.isChecked()
            self.build_target.project.source_dir = self.source_edit.text()

            self.session.commit()
            print(f"BuildTarget {self.build_target.id} - {self.build_target.target_platform} saved.")
            self.build_target_created.emit(self.build_target.id)
            super().accept()
            
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save: {str(e)}")
            self.reject()

    def reject(self):
        self.session.rollback()
        self.session.close()
        if self.vcs_client:
            self.vcs_client._disconnect()
        super().reject()

    def closeEvent(self, event):
        if self.session.dirty:
            reply = QMessageBox.question(
                self, "Unsaved Changes", "You have unsaved changes. Close anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.reject()
                event.accept()
            else:
                event.ignore()
        else:
            self.reject()
            event.accept()