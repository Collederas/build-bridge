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
    QMessageBox,
)
from PyQt6.QtCore import Qt
from app_config import ConfigManager

logger = logging.getLogger(__name__)


class SteamBuildSetupWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Steam Build Setup Wizard")
        self.config_manager = ConfigManager("stores")
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
        
        # Use app_id from config if available
        app_id = self.config_manager.get("steam.app_id", "")
        self.app_id_input = QLineEdit(app_id)
        form_layout.addRow(QLabel("App ID:"), self.app_id_input)
        
        # Use description from config or default
        description = self.config_manager.get("steam.description", "My Game Build v1.0")
        self.description_input = QLineEdit(description)
        form_layout.addRow(QLabel("Description:"), self.description_input)
        layout.addLayout(form_layout)

        layout.addWidget(
            QLabel(
                "Depot IDs are assigned in Steamworks. Please create your depots in the "
                "Steamworks App Admin panel, then enter their IDs below (one per line):"
            )
        )
        
        # Get depot IDs from config if available
        self.depot_input = QTextEdit()
        depots = self.config_manager.get("steam.depots", [])
        if depots:
            self.depot_input.setPlainText("\n".join(depots))
        else:
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
        self.depot_layout = QFormLayout()
        page.setLayout(self.depot_layout)
        page.initializePage = self.initialize_depot_page
        return page

    def initialize_depot_page(self):
        # Clear existing layout contents
        for i in reversed(range(self.depot_layout.count())):
            widget = self.depot_layout.itemAt(i).widget() if self.depot_layout.itemAt(i) else None
            if widget:
                widget.deleteLater()

        self.depots.clear()
        depot_text = self.depot_input.toPlainText().strip()
        depot_ids = [d.strip() for d in depot_text.split("\n") if d.strip()]
        
        # Get depot paths from config if available
        depot_paths = self.config_manager.get("steam.depot_paths", {})
        
        for depot_id in depot_ids:
            # Use stored path if available, otherwise use build path
            default_path = depot_paths.get(depot_id, self.build_path)
            path_input = QLineEdit(default_path)
            
            browse_btn = QPushButton("Browse")
            browse_btn.clicked.connect(
                lambda _, p=path_input: (
                    p.setText(selected) if (selected := QFileDialog.getExistingDirectory(self, "Select Depot Path", p.text())) else None
                )
            )
            self.depot_layout.addRow(QLabel(f"Depot {depot_id} Path:"), path_input)
            self.depot_layout.addRow("", browse_btn)
            self.depots.append((depot_id, path_input))

    def create_builder_page(self):
        page = QWizardPage()
        page.setTitle("Set Up Builder Folder")
        layout = QVBoxLayout()

        # Use builder path from config or generate default
        saved_builder_path = self.config_manager.get("steam.builder_path", "")
        if saved_builder_path:
            builder_path = saved_builder_path
        else:
            builder_path = os.path.normpath(os.path.join(self.build_path, "Steam/builder"))
            
        self.builder_path_input = QLineEdit(builder_path)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(
            lambda: (
                self.builder_path_input.setText(selected) if (selected := QFileDialog.getExistingDirectory(self, "Select Builder Path", self.builder_path_input.text())) else None
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
        self.review_label.setWordWrap(True)
        
        layout = QVBoxLayout()
        layout.addWidget(self.review_label)
        
        # Add a note about saving to config
        save_note = QLabel("The configuration will be saved to the application's configuration when you click Finish.")
        save_note.setWordWrap(True)
        layout.addWidget(save_note)
        
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

    def accept(self):
        """Override accept to save config before closing the wizard"""
        if self.save_config():
            self.generate_files()
            super().accept()
        else:
            QMessageBox.warning(
                self,
                "Configuration Error",
                "Failed to save configuration. Please check your inputs."
            )

    def save_config(self):
        """Save the configuration values to the ConfigManager"""
        try:
            # Save app ID
            app_id = self.field("app_id")
            self.config_manager.set("steam.app_id", app_id)
            
            # Save description
            description = self.description_input.text()
            self.config_manager.set("steam.description", description)
            
            # Save builder path
            builder_path = self.field("builder_path")
            self.config_manager.set("steam.builder_path", builder_path)
            
            # Save depots
            depot_ids = [depot_id for depot_id, _ in self.depots]
            self.config_manager.set("steam.depots", depot_ids)
            
            # Save depot paths
            depot_paths = {}
            for depot_id, path_input in self.depots:
                depot_paths[depot_id] = path_input.text()
            self.config_manager.set("steam.depot_paths", depot_paths)
            
            # Mark as enabled
            self.config_manager.set("steam.enabled", True)
            
            # Save the config to disk
            return self.config_manager.save()
            
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def generate_files(self):
        """Generate the VDF files needed for Steam deployment"""
        app_id = self.field("app_id")
        description = self.description_input.text()
        builder_path = self.field("builder_path")

        try:
            # Create builder directory if it doesn't exist
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
                depot_path = path_input.text().replace("\\", "/")  # Steam uses forward slashes
                depot_vdf_content = f""""depotbuild"
{{
    "depotid" "{depot_id}"
    "contentroot" "{depot_path}"
}}"""
                with open(
                    os.path.join(builder_path, f"depot_build_{depot_id}.vdf"), "w"
                ) as f:
                    f.write(depot_vdf_content)

            logger.info(f"Generated Steam build files in {builder_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to generate files: {e}")
            QMessageBox.critical(
                self,
                "File Generation Error",
                f"Failed to generate Steam build files: {str(e)}"
            )
            return False