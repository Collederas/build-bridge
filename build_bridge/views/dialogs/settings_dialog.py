import os, logging
from tkinter import N
from PyQt6.QtCore import pyqtSignal
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
    QFileDialog,
    QTextEdit,
)
from PyQt6.QtGui import QColor, QIcon

from build_bridge.core.vcs.p4client import P4Client

from build_bridge.database import SessionFactory
from build_bridge.exceptions import InvalidConfigurationError
from build_bridge.models import Project, PerforceConfig
from build_bridge.utils.paths import get_resource_path
from build_bridge.views.widgets.config_widget_steam import SteamConfigWidget
from build_bridge.views.widgets.config_widget_itch import ItchConfigWidget


class SettingsDialog(QDialog):
    monitored_dir_changed_signal = pyqtSignal(str)

    def __init__(self, parent=None, default_page: int = 0):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(600, 400)
        icon_path = str(get_resource_path("build_bridge/icons/buildbridge.ico"))
        self.setWindowIcon(QIcon(icon_path))

        self.default_page = default_page

        # DIALOG MANAGED SESSION: all settings are saved as single transaction
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
                logging.info("Settings: No project found, creating new project")
                self.project = Project()
                self.project.name = ""
                self.project.source_dir = ""
                self.project.archive_directory = ""
                self.session.add(self.project)
                self.session.commit()  # Save immediately to ensure it has an ID
            else:
                logging.info(f"Settings: Found existing project: '{self.project.name}'")
                # Ensure project is attached to our session
                if self.project not in self.session:
                    self.session.add(self.project)
        except Exception as e:
            logging.info("Settings: Error loading project: {str(e)}")
            self.project = None

    def setup_ui(self):
        layout = QHBoxLayout()

        self.category_list = QListWidget()
        self.category_list.addItems(["Project", "Steam", "Itch"])
        layout.addWidget(self.category_list, 1)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.create_project_page())

        # TODO: VCS
        # self.stack.addWidget(self.create_vcs_page())

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
        curr_dir = self.archive_dir_input.text().strip()
        if os.path.isdir(curr_dir):
            new_folder = QFileDialog.getExistingDirectory(self, "Select Archive Directory", curr_dir)
        else:
            new_folder = QFileDialog.getExistingDirectory(self, "Select Archive Directory")

        if new_folder:
            self.archive_dir_input.setText(new_folder)

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
        """Load existing data from build_bridge.database into UI fields."""
        if not self.project:
            logging.info("Settings: Warning: No project available to load data from")
            return

        try:
            # Explicitly refresh from build_bridge.database to ensure we have latest data
            self.session.refresh(self.project)

            # Load data into form fields
            self.project_name_input.setText(self.project.name or "")
            self.source_dir_input.setText(self.project.source_dir or "")
            arch_dir = self.project.archive_directory
            self.archive_dir_input.setText(arch_dir or "")
            self._initial_archive_dir = (
                arch_dir  # monitored here to emit signal later if changed
            )

        except Exception as e:
            logging.info("Settings: Error loading form data: {str(e)}")

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)

    def apply_settings(self):
        errors_occurred = []

        # PROJECT SETTINGS -> perhaps move to own widget

        # Create project if it doesnt exist
        try:
            if not self.project:
                self.project = Project()

            # Update project with form values
            self.project.name = self.project_name_input.text().strip()
            self.project.source_dir = self.source_dir_input.text().strip()
            self.project.archive_directory = self.archive_dir_input.text().strip()

            if self.project not in self.session:
                self.session.add(self.project)

            # TODO: PERFORCE SETTINGS
            # This should be moved to self contained widget
            # try:
            #     self.perforce_config.user = self.p4_user_input.text().strip()
            #     self.perforce_config.p4password = self.p4_password_input.text().strip()
            #     self.perforce_config.server_address = (
            #         self.p4_server_input.text().strip()
            #     )
            #     self.perforce_config.client = self.p4_client_input.text().strip()
            #     self.session.add(self.perforce_config)
            #     logging.info("Settings: saving vcs settings: user {self.p4_user_input.text().strip()}")

            # except Exception as e:
            #     logging.info("Settings: Error saving Perforce settings: {str(e)}")
            #     QMessageBox.critical(
            #         self, "Error", f"Failed to save Perforce settings: {str(e)}"
            #     )

            # if self.perforce_config not in self.session:
            #     self.session.add(self.perforce_config)
            #

            # Validate Steam, store password
            try:
           
                self.steam_config_widget.validate()  # raises ValueError for model vlaidation and InvalidConfigurationError for widget validated errors
      
    
                self.steam_config_widget.store_password()
                logging.info(
                    "Settings: Steam settings validated. Keyring saved."
                )

                self.session.add(self.steam_config_widget.steam_config)

            except (InvalidConfigurationError, ValueError) as e:
                error_msg = f"Failed to save Steam settings: {str(e)}"
                logging.info(error_msg)
                errors_occurred.append(error_msg)


            # Validate Itch, store api_key if username provided too
            try:
               
                self.itch_config_widget.validate() # raises ValueError for model vlaidation and InvalidConfigurationError for widget validated errors
             
                self.session.add(self.itch_config_widget.itch_config)
                
                self.itch_config_widget.store_api_key()
                logging.info(
                    "Settings: Itch settings validated. Keyring saved."
                )
            except (InvalidConfigurationError, ValueError) as e:
                error_msg = f"Failed to save Itch.io settings: {str(e)}"
                logging.info(error_msg)
                errors_occurred.append(error_msg)

            # Commit changes to the database and ensure they're flushed

            self.session.commit()
            self.session.flush()

            if self._initial_archive_dir != self.project.archive_directory:
                self.monitored_dir_changed_signal.emit(str(self.project.builds_path))

            logging.info("Settings: Commit successful")

            logging.info(
                f"Settings: Saving project - Name: '{self.project.name}', Source: '{self.project.source_dir}', Builds will be stored in: '{self.project.builds_path}'"
            )

            if errors_occurred:
                # Inform user about non-critical failures AFTER successful commit of essentials
                logging.info(
                    "Settings: Errors occurred saving some settings:\n\n"
                    + "\n".join(errors_occurred)
                )
            else:
                logging.info(
                    "Settings: All settings saved successfully. User can publish to all platforms!"
                )

            self.accept()
        except Exception as e:
            # CRITICAL FAILURE -> causes settings roll back
            # This catches errors during essential data preparation or the final commit itself.
            logging.info(f"CRITICAL Error saving settings: {str(e)}")
            try:
                self.session.rollback()
                logging.info("Session rolled back due to critical error.")
            except Exception as rb_e:
                logging.info(f"Error during rollback: {rb_e}")

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
