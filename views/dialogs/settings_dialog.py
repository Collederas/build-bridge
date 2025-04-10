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
    QFileDialog,
    QTextEdit,
)
from PyQt6.QtGui import QColor
from core.vcs.p4client import P4Client

from database import SessionFactory
from models import Project, PerforceConfig
from views.widgets.steam_config_widget import SteamConfigWidget
from views.widgets.itch_config_widget import ItchConfigWidget


class SettingsDialog(QDialog):
    def __init__(self, parent=None, default_page: int = 0):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(600, 400)
        self.default_page = default_page

        # Dialog managed session
        self.session = SessionFactory()

        # Query for project and ensure it exists
        self.load_project()
        self.setup_ui()
        self.load_form_data()  # Load data into UI fields after setting up UI

    def load_project(self):
        """Ensure project exists and is attached to session"""
        try:
            # Query for existing project
            self.project = self.session.query(Project).first()

            # If no project exists, create one
            if not self.project:
                print("No project found, creating new project")
                self.project = Project()
                self.project.name = ""
                self.project.source_dir = ""
                self.project.dest_dir = ""
                self.project.archive_directory = ""
                self.session.add(self.project)
                self.session.commit()  # Save immediately to ensure it has an ID
            else:
                print(f"Found existing project: '{self.project.name}'")
                # Ensure project is attached to our session
                if self.project not in self.session:
                    self.session.add(self.project)
        except Exception as e:
            print(f"Error loading project: {str(e)}")
            self.project = None

    def setup_ui(self):
        layout = QHBoxLayout()

        self.category_list = QListWidget()
        self.category_list.addItems(["Project", "Steam", "Itch"])
        layout.addWidget(self.category_list, 1)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.create_project_page())
        self.stack.addWidget(self.create_vcs_page())
        self.steam_config_widget = SteamConfigWidget(self.session)
        self.itch_config_widget = ItchConfigWidget(self.session)
        self.stack.addWidget(self.steam_config_widget)
        self.stack.addWidget(self.itch_config_widget)

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

        self.project_name_input = QLineEdit()
        self.source_dir_input = QLineEdit()
        self.dest_dir_input = QLineEdit()
        self.archive_dir_input = QLineEdit()

        # Project Name field
        form_layout.addRow(QLabel("Project Name:"), self.project_name_input)

        # Source directory field
        form_layout.addRow(QLabel("Source Directory:"), self.source_dir_input)
        source_browse_button = QPushButton("Browse")
        source_browse_button.clicked.connect(self.browse_project_folder)
        form_layout.addWidget(source_browse_button)

        # Archive directory field
        form_layout.addRow(QLabel("Archive Directory:"), self.archive_dir_input)
        archive_browse_button = QPushButton("Browse")
        archive_browse_button.clicked.connect(self.browse_archive_directory)
        form_layout.addWidget(archive_browse_button)

        layout.addLayout(form_layout)
        page.setLayout(layout)
        return page

    def browse_project_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Project Folder")
        if folder:
            self.source_dir_input.setText(folder)

    def browse_archive_directory(self):
        """Open a file dialog to select the archive directory."""
        folder = QFileDialog.getExistingDirectory(self, "Select Archive Directory")
        if folder:
            self.archive_dir_input.setText(folder)

    def create_vcs_page(self):
        page = QWidget()
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # Load or create Perforce configuration
        self.perforce_config = (
            self.session.query(PerforceConfig)
            .order_by(PerforceConfig.id.desc())
            .first()
        )
        if not self.perforce_config:
            self.perforce_config = PerforceConfig()
            self.session.add(self.perforce_config)

        # Perforce settings
        self.p4_user_input = QLineEdit(self.perforce_config.user or "")
        form_layout.addRow(QLabel("Perforce User:"), self.p4_user_input)

        self.p4_password_input = QLineEdit(self.perforce_config.p4password or "")
        self.p4_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow(QLabel("Perforce Password:"), self.p4_password_input)

        # Add note about keyring usage with better styling
        keyring_note = QLabel(
            "Note: The Perforce password is securely stored using the system keyring and will not be saved in the application database."
        )
        keyring_note.setWordWrap(True)
        keyring_note.setStyleSheet("font-style: italic; color: gray;")  # Subtle styling
        form_layout.addRow("", keyring_note)  # Empty label for alignment

        self.p4_server_input = QLineEdit(self.perforce_config.server_address or "")
        form_layout.addRow(QLabel("Perforce Server:"), self.p4_server_input)

        self.p4_client_input = QLineEdit(self.perforce_config.client or "")
        form_layout.addRow(QLabel("Perforce Client:"), self.p4_client_input)

        # Test Connection Button with spacing
        self.test_connection_btn = QPushButton("Test Connection")
        self.test_connection_btn.clicked.connect(self.test_p4_connection)
        form_layout.addRow("", self.test_connection_btn)  # Empty label for alignment
        form_layout.setSpacing(10)  # Add spacing between rows

        # Connection Status Display with slight padding
        self.connection_status_display = QTextEdit()
        self.connection_status_display.setReadOnly(True)
        self.connection_status_display.setMaximumHeight(50)
        self.connection_status_display.setStyleSheet("padding: 5px;")  # Add padding
        form_layout.addRow(
            "", self.connection_status_display
        )  # Empty label for alignment

        layout.addLayout(form_layout)
        layout.addStretch()  # Push content to top, leaving space below
        page.setLayout(layout)
        return page

    def test_p4_connection(self):
        """Test the Perforce connection and display the result."""
        try:
            # Create a temporary Perforce client with the current settings
            temp_config = PerforceConfig(
                user=self.p4_user_input.text().strip(),
                server_address=self.p4_server_input.text().strip(),
                client=self.p4_client_input.text().strip(),
            )
            temp_config.p4password = self.p4_password_input.text().strip()

            p4_client = P4Client(config=temp_config)
            p4_client.ensure_connected()  # Test connection

            # Display success message
            self.display_connection_status("Connection successful", QColor("green"))
        except Exception as e:
            # Display error message
            self.display_connection_status(
                f"Connection failed: {str(e)}", QColor("red")
            )

    def display_connection_status(self, message, color):
        """Display a connection status message with the specified color."""
        self.connection_status_display.setTextColor(color)
        self.connection_status_display.setText(message)

    def load_form_data(self):
        """Load existing data from database into UI fields"""
        if not self.project:
            print("Warning: No project available to load data from")
            return

        try:
            # Explicitly refresh from database to ensure we have latest data
            self.session.refresh(self.project)

            # Load data into form fields
            print(
                f"Loading form data - Name: '{self.project.name}', Source: '{self.project.source_dir}', Archive: '{self.project.archive_directory}'"
            )

            self.project_name_input.setText(self.project.name or "")
            self.source_dir_input.setText(self.project.source_dir or "")
            self.archive_dir_input.setText(self.project.archive_directory or "")
        except Exception as e:
            print(f"Error loading form data: {str(e)}")

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)

    def apply_settings(self):
        # Save project settings
        try:
            if not self.project:
                self.project = Project()
                self.session.add(self.project)

            # Update project with form values
            self.project.name = self.project_name_input.text().strip()
            self.project.source_dir = self.source_dir_input.text().strip()
            self.project.dest_dir = self.dest_dir_input.text().strip()
            self.project.archive_directory = self.archive_dir_input.text().strip()

            # Debug values being saved
            print(
                f"Saving project - Name: '{self.project.name}', Source: '{self.project.source_dir}', Dest: '{self.project.dest_dir}', Archive: '{self.project.archive_directory}'"
            )

            # Save Perforce settings
            try:
                self.perforce_config.user = self.p4_user_input.text().strip()
                self.perforce_config.p4password = self.p4_password_input.text().strip()
                self.perforce_config.server_address = (
                    self.p4_server_input.text().strip()
                )
                self.perforce_config.client = self.p4_client_input.text().strip()
                self.session.add(self.perforce_config)
                print(f"saving vcs settings: user {self.p4_user_input.text().strip()}")

            except Exception as e:
                print(f"Error saving Perforce settings: {str(e)}")
                QMessageBox.critical(
                    self, "Error", f"Failed to save Perforce settings: {str(e)}"
                )

            # Make sure object is in session
            if self.project not in self.session:
                self.session.add(self.project)

            self.steam_config_widget.save_settings()
            self.itch_config_widget.save_settings()

            # Commit changes to the database and ensure they're flushed
            self.session.commit()
            self.session.flush()

            print(f"VCS Saved: user {self.perforce_config.user}")
            print(
                f"Project saved: '{self.project.name}' (ID: {self.project.id if hasattr(self.project, 'id') else 'unknown'})"
            )

            self.accept()
        except Exception as e:
            print(f"Error saving settings: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to save settings: {str(e)}")
            self.reject()

    def accept(self):
        """User clicked Apply - close dialog but keep session open"""
        # Close session if we created it
        try:
            self.steam_config_widget.cleanup()
            self.session.close()
        except:
            pass
        super().accept()

    def reject(self):
        """User clicked Cancel - rollback any changes"""
        self.steam_config_widget.cleanup()
        try:
            self.session.rollback()
        except:
            pass  # Session might already be invalid
        finally:
            # Only close the session if we created it
            try:
                self.session.close()
            except:
                pass
            super().reject()

    def closeEvent(self, event):
        """Handle window close button (same as reject)"""
        self.reject()
        event.accept()
