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
    QPushButton,
    QMessageBox,
)

from PyQt6.QtCore import Qt
from sqlalchemy.orm import Session
from database import SessionFactory
from models.project import Project


class SettingsDialog(QDialog):
    def __init__(self, parent=None, default_page: int = 0):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(600, 400)
        self.default_page = default_page

        # Initialize SQLAlchemy session
        self.session: Session = SessionFactory()

        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout()

        self.category_list = QListWidget()
        self.category_list.addItems(["Project", "Version Control"])
        layout.addWidget(self.category_list, 1)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.create_project_page())
        self.stack.addWidget(self.create_vcs_page())

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
        self.category_list.currentRowChanged.connect(self.switch_page)

        self.category_list.setCurrentRow(self.default_page)

    def create_project_page(self):
        page = QWidget()
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # Project name field
        self.project_name_input = QLineEdit(self.project.name)
        form_layout.addRow(QLabel("Project Name:"), self.project_name_input)

        # Source directory field
        self.source_dir_input = QLineEdit(self.project.source_dir)
        form_layout.addRow(QLabel("Source Directory:"), self.source_dir_input)

        # Destination directory field
        self.dest_dir_input = QLineEdit(self.project.dest_dir)
        form_layout.addRow(QLabel("Destination Directory:"), self.dest_dir_input)

        layout.addLayout(form_layout)
        page.setLayout(layout)
        return page

    def create_vcs_page(self):
        page = QWidget()
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # VCS settings
        vcs_config = self.vcs_config
        self.vcs_user_input = QLineEdit(vcs_config.vcs_user or "")
        form_layout.addRow(QLabel("VCS User:"), self.vcs_user_input)

        self.vcs_password_input = QLineEdit(vcs_config.vcs_password or "")
        self.vcs_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow(QLabel("VCS Password:"), self.vcs_password_input)

        self.vcs_port_input = QLineEdit(vcs_config.vcs_port or "")
        form_layout.addRow(QLabel("VCS Port:"), self.vcs_port_input)

        self.vcs_client_input = QLineEdit(vcs_config.vcs_client or "")
        form_layout.addRow(QLabel("VCS Client:"), self.vcs_client_input)

        layout.addLayout(form_layout)
        page.setLayout(layout)
        return page

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)

    def apply_settings(self):
        # Save project settings
        self.project.name = self.project_name_input.text().strip()
        self.project.source_dir = self.source_dir_input.text().strip()
        self.project.dest_dir = self.dest_dir_input.text().strip()

        # Save VCS settings
        vcs_config = self.vcs_config
        vcs_config.vcs_user = self.vcs_user_input.text().strip()
        vcs_config.vcs_password = self.vcs_password_input.text().strip()
        vcs_config.vcs_port = self.vcs_port_input.text().strip()
        vcs_config.vcs_client = self.vcs_client_input.text().strip()

        # Commit changes to the database
        self.session.commit()
        self.accept()
