import sys
from PyQt6.QtWidgets import (
    QApplication,
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
)
from PyQt6.QtCore import Qt

from models.build_target import BuildTarget
from database import SessionContext, SessionFactory
from models.project import Project
from views.dialogs.settings_dialog import SettingsDialog


class BuildTargetSetupDialog(QDialog):
    def __init__(self, project: Project):
        super().__init__()
        self.setWindowTitle("Build Target Setup")
        self.setMinimumSize(800, 500)

        # Initialize SQLAlchemy session
        self.session = SessionFactory()
        self.project = self.session.query(Project).first()

        self.build_target = self.session.query(BuildTarget).first()

        self.stack = QStackedWidget()
        self.page1 = self.create_page1()
        self.page2 = self.create_page2()

        self.stack.addWidget(self.page1)
        self.stack.addWidget(self.page2)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.addLayout(self.add_header("Build Target"))
        self.main_layout.addWidget(self.stack)
        self.main_layout.addLayout(self.create_footer())

        self.load_target_data()


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
        self.project_combo.addItems([self.project.name])

        self.source_edit = QLineEdit(self.project.source_dir)
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
            "You can setup VCS to let BuildBridge switch automatically to\n"
            "target branch and use the branch name as release name."
        )
        vcs_desc.setWordWrap(True)
        vcs_desc.setStyleSheet("color: gray; font-size: 11px;")

        self.vcs_combo = QComboBox()
        self.vcs_combo.addItems(["Git"])
        vcs_type_layout = QHBoxLayout()
        vcs_type_layout.addWidget(QLabel("VCS Type:"))
        vcs_type_layout.addWidget(self.vcs_combo)

        vcs_settings_button = QPushButton("Setup VCS")
        vcs_settings_button.clicked.connect(self.open_vcs_settings)
        vcs_type_layout.addWidget(vcs_settings_button)

        self.branch_combo = QComboBox()
        self.branch_combo.addItems([""])
        branch_layout = QHBoxLayout()
        branch_layout.addWidget(QLabel("Target Branch:"))
        branch_layout.addWidget(self.branch_combo)

        layout.addWidget(vcs_title)
        layout.addWidget(vcs_desc)
        layout.addSpacing(10)
        layout.addLayout(vcs_type_layout)
        layout.addLayout(branch_layout)
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
        self.build_id_edit = QLineEdit("0.2_dev")
        self.build_type_combo = QComboBox()
        self.build_type_combo.addItems(["Shipping"])
        self.target_platform_combo = QComboBox()
        self.target_platform_combo.addItems(["Win 64"])

        self.optimize_checkbox = QCheckBox("Optimize Packaging for Steam")
        self.optimize_hint = QLabel(
            "Will build using Valve\nRecommended padding alignment values"
        )
        self.optimize_hint.setStyleSheet("color: gray; font-size: 10px;")
        self.optimize_hint.setWordWrap(True)

        optimize_layout = QVBoxLayout()
        optimize_layout.addWidget(self.optimize_checkbox)
        optimize_layout.addWidget(self.optimize_hint)

        form.addRow("Build ID", self.build_id_edit)
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
        folder = QFileDialog.getExistingDirectory(self, "Select Project Folder")
        if folder:
            self.source_edit.setText(folder)

    def open_vcs_settings(self):
        settings_dialog = SettingsDialog(default_page=1)
        result = settings_dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            self.vc

    def load_target_data(self):
        # Build ID
        if self.build_target:
            self.build_id_edit.setText(str(self.build_target.build_id))

            # VCS type
            vcs_index = self.vcs_combo.findText(self.build_target.vcs_type)
            if vcs_index >= 0:
                self.vcs_combo.setCurrentIndex(vcs_index)

            # Target branch
            current_branch = self.build_target.target_branch or ""
            if self.branch_combo.findText(current_branch) == -1:
                self.branch_combo.addItem(current_branch)
            self.branch_combo.setCurrentText(current_branch)

            # Build type
            if self.build_target.build_type == "dev":
                self.build_type_combo.setCurrentText("Development")
            else:
                self.build_type_combo.setCurrentText("Shipping")

            # Target platform
            platform_map = {
                "win_64": "Win 64",
                "win_32": "Win 32",
                "mac_os": "Mac OS"
            }
            readable_platform = platform_map.get(self.build_target.target_platform, "Win 64")
            self.target_platform_combo.setCurrentText(readable_platform)

            # Optimize for Steam
            self.optimize_checkbox.setChecked(bool(self.build_target.optimize_for_steam))

            # Preselect Project Name in combo (assuming project is loaded separately)
            if self.build_target.project:
                project_name = self.project.name
                index = self.project_combo.findText(project_name)
                if index == -1:
                    self.project_combo.addItem(project_name)
                    index = self.project_combo.findText(project_name)
                self.project_combo.setCurrentIndex(index)

                # Load source directory
                self.source_edit.setText(self.build_target.project.source_dir)

    def accept(self):
        # Create a new BuildTarget if it doesn't exist
        if not self.build_target:
            self.build_target = BuildTarget()
            self.build_target.project = self.project
            self.session.add(self.build_target)

        # Map UI -> self.target model fields
        self.build_target.build_id = self.build_id_edit.text()

        # Map VCS type
        vcs_text = self.vcs_combo.currentText().lower()
        self.build_target.vcs_type = vcs_text if vcs_text in ["git", "perforce"] else "perforce"

        # Target branch
        self.build_target.target_branch = self.branch_combo.currentText()

        # Build type
        build_type_text = self.build_type_combo.currentText().lower()
        if build_type_text == "development":
            self.build_target.build_type = "dev"
        else:
            self.build_target.build_type = "prod"

        # Target platform
        platform_text = self.target_platform_combo.currentText().lower().replace(" ", "_")
        if platform_text == "win_64":
            self.build_target.target_platform = "win_64"
        elif platform_text == "win_32":
            self.build_target.target_platform = "win_32"
        else:
            self.build_target.target_platform = "mac_os"

        # Steam optimization
        self.build_target.optimize_for_steam = self.optimize_checkbox.isChecked()

        # Save source directory
        self.build_target.project.source_dir = self.source_edit.text()

        # Commit to DB
        self.session.commit()

        # Close dialog
        super().accept()

