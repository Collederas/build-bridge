import os
import logging
from PyQt6.QtWidgets import (
    QWizard,
    QWizardPage,
    QVBoxLayout,
    QFormLayout,
    QPushButton,
    QLineEdit,
    QLabel,
    QTextEdit,
    QFileDialog,
)
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)


class SteamBuildSetupWizard(QWizard):
    def __init__(self, build_path, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Steam Build Setup Wizard")
        self.build_path = os.path.normpath(build_path)
        self.config = config
        self.depots = []
        self.setup_pages()

    def setup_pages(self):
        self.addPage(self.create_intro_page())
        self.addPage(self.create_app_page())
        self.addPage(self.create_depot_page())
        self.addPage(self.create_builder_page())
        self.addPage(self.create_review_page())

    def create_intro_page(self):
        page = QWizardPage()
        page.setTitle("Welcome to Steam Build Setup")
        layout = QVBoxLayout()
        layout.addWidget(
            QLabel(
                "This wizard will help you create the necessary files (`app_build.vdf`, `depot_build.vdf`, "
                "and builder folder) to publish your build to Steam. Click Next to begin."
            )
        )
        page.setLayout(layout)
        return page

    def create_app_page(self):
        page = QWizardPage()
        page.setTitle("Configure Your Steam App")
        layout = QVBoxLayout()

        form_layout = QFormLayout()
        self.app_id_input = QLineEdit(self.config.get("app_id", ""))
        form_layout.addRow(QLabel("App ID:"), self.app_id_input)
        self.description_input = QLineEdit("My Game Build v1.0")
        form_layout.addRow(QLabel("Description:"), self.description_input)
        layout.addLayout(form_layout)

        layout.addWidget(
            QLabel(
                "Depot IDs are assigned in Steamworks. Please create your depots in the "
                "Steamworks App Admin panel, then enter their IDs below (one per line):"
            )
        )
        self.depot_input = QTextEdit()
        self.depot_input.setPlaceholderText("1234561\n1234562")
        self.depot_input.setFixedHeight(100)  # Limit height for readability
        layout.addWidget(self.depot_input)

        page.setLayout(layout)
        page.registerField("app_id*", self.app_id_input)
        self.app_id_input.textChanged.connect(page.completeChanged)
        self.depot_input.textChanged.connect(page.completeChanged)
        page.isComplete = lambda: self.is_app_page_complete()

        return page

    def is_app_page_complete(self):
        """Check if the page is complete for navigation."""
        app_id = self.app_id_input.text().strip()
        depot_text = self.depot_input.toPlainText().strip()
        depots = [d.strip() for d in depot_text.split("\n") if d.strip()]
        return bool(app_id and depots and all(d.isdigit() for d in depots))

    def create_depot_page(self):
        page = QWizardPage()
        page.setTitle("Configure Depot Content")
        self.depot_layout = QFormLayout()  # Change to QFormLayout
        page.setLayout(self.depot_layout)
        page.initializePage = self.initialize_depot_page
        return page

    def initialize_depot_page(self):
        # Clear existing layout contents
        for i in reversed(range(self.depot_layout.count())):
            self.depot_layout.takeAt(i).widget().deleteLater() if self.depot_layout.itemAt(i) else None

        self.depots.clear()
        depot_text = self.depot_input.toPlainText().strip()
        depot_ids = [d.strip() for d in depot_text.split("\n") if d.strip()]
        for depot_id in depot_ids:
            path_input = QLineEdit(self.build_path)
            browse_btn = QPushButton("Browse")
            browse_btn.clicked.connect(
                lambda _, p=path_input: (
                    p.setText(selected) if (selected := QFileDialog.getExistingDirectory(self, "Select Depot Path", self.build_path)) else None
                )
            )
            self.depot_layout.addRow(QLabel(f"Depot {depot_id} Path:"), path_input)
            self.depot_layout.addRow("", browse_btn)
            self.depots.append((depot_id, path_input))

    def create_builder_page(self):
        page = QWizardPage()
        page.setTitle("Set Up Builder Folder")
        layout = QVBoxLayout()

        builder_path = os.path.normpath(os.path.join(self.build_path, "Steam/builder"))
        self.builder_path_input = QLineEdit(builder_path)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(
            lambda: (
                self.builder_path_input.setText(selected) if (selected := QFileDialog.getExistingDirectory(self, "Select Builder Path", builder_path)) else None
            )
        )
        form_layout = QFormLayout()
        form_layout.addRow(QLabel("Builder Path:"), self.builder_path_input)
        form_layout.addRow("", browse_btn)
        layout.addLayout(form_layout)
        layout.addWidget(
            QLabel("This folder will contain your VDF files and content for SteamCMD.")
        )

        page.setLayout(layout)
        page.registerField("builder_path*", self.builder_path_input)
        self.builder_path_input.textChanged.connect(page.completeChanged)
        page.isComplete = lambda: self.is_builder_page_complete()

        return page

    def is_builder_page_complete(self):
        """Check if the builder path is valid for navigation."""
        builder_path = self.builder_path_input.text().strip()
        return bool(builder_path)

    def create_review_page(self):
        page = QWizardPage()
        page.setTitle("Review and Generate")
        self.review_label = QLabel()
        layout = QVBoxLayout()
        layout.addWidget(self.review_label)
        page.setLayout(layout)
        page.initializePage = self.update_review
        return page

    def update_review(self):
        app_id = self.field("app_id")
        description = self.description_input.text()
        builder_path = self.field("builder_path")
        depot_summary = "\n".join(
            [
                f"- Depot {depot_id} mapped to {path.text()}"
                for depot_id, path in self.depots
            ]
        )
        self.review_label.setText(
            f"Create `app_build.vdf` with:\n- App ID: {app_id}\n- Description: {description}\n"
            f"{depot_summary}\n\nSet up builder folder at: {builder_path}"
        )

    def generate_files(self):
        app_id = self.field("app_id")
        description = self.description_input.text()
        builder_path = self.field("builder_path")

        os.makedirs(builder_path, exist_ok=True)

        # Generate app_build.vdf
        app_vdf_content = f""""appbuild"
{{
    "appid" "{app_id}"
    "desc" "{description}"
    "buildoutput" "{builder_path}"
    "depots"
    {{
        {chr(10).join([f'        "{depot_id}" "depot_build_{depot_id}.vdf"' for depot_id, _ in self.depots])}
    }}
}}"""
        with open(os.path.join(builder_path, "app_build.vdf"), "w") as f:
            f.write(app_vdf_content)

        # Generate depot_build.vdf for each depot
        for depot_id, path_input in self.depots:
            depot_vdf_content = f""""depotbuild"
{{
    "depotid" "{depot_id}"
    "contentroot" "{path_input.text()}"
}}"""
            with open(
                os.path.join(builder_path, f"depot_build_{depot_id}.vdf"), "w"
            ) as f:
                f.write(depot_vdf_content)

        logger.info(f"Generated Steam build files in {builder_path}")
