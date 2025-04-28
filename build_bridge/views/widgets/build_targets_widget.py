import os, logging
from pathlib import Path
import shutil

from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QFrame,
    QSizePolicy,
    QSpacerItem,
    QMessageBox,
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont

from build_bridge.core.builder.unreal_builder import (
    EngineVersionError,
    ProjectFileNotFoundError,
    UnrealBuilder,
    UnrealEngineNotInstalledError,
)
from build_bridge.database import session_scope
from build_bridge.models import BuildTarget
from build_bridge.views.dialogs.build_dialog import BuildWindowDialog
from build_bridge.views.dialogs.build_target_setup_dialog import BuildTargetSetupDialog


class BuildTargetListWidget(QWidget):
    """Lists the available Build Targets or shows an Add button."""

    build_ready_signal = pyqtSignal()

    def __init__(self, build_target_id: int | None, parent=None):  # Accept ID
        super().__init__()
        self.parent = parent
        self.vcs_client = parent.vcs_client if parent else None
        self._build_target_id = build_target_id  # Store the ID

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)  # Keep outer margins

        heading_label = QLabel("Build Target")
        heading_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        outer_layout.addWidget(heading_label)

        self.contrast_frame = QFrame()
        self.contrast_frame.setObjectName("contrastFrame")
        self.contrast_frame.setFrameShape(QFrame.Shape.StyledPanel)
        # Slightly reduced padding inside the frame for tighter look
        self.contrast_frame.setStyleSheet(
            """
            QFrame#contrastFrame {
                background-color: #f9f9f9; /* Lighter gray */
                border: 1px solid #d0d0d0; /* Slightly softer border */
                border-radius: 5px;       /* Slightly smaller radius */
                padding: 8px;
            }
            """
        )

        self.content_layout = QHBoxLayout(self.contrast_frame)
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        self.content_layout.setSpacing(8)  # Slightly reduced spacing

        display_name_font = QFont()
        display_name_font.setBold(True)
        self.target_label = QLabel()
        self.target_label.setFont(display_name_font)
        self.target_label.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred
        )

        self.build_version_label = QLabel("Build Version:")
        self.build_version_input = QLineEdit("0.1")
        self.build_version_input.setMaximumWidth(80)
        self.build_version_input.setToolTip(
            "Enter the desired version string for this build (e.g., 1.0, 0.2-beta)"
        )

        self.edit_button = QPushButton("Edit")
        self.build_button = QPushButton("Build")

        # Widget for the "No Build Target" state ---
        self.add_button = QPushButton("+ Add new Build Target")

        self.content_layout.addWidget(self.target_label)

        self.content_layout.addStretch(1)

        self.content_layout.addWidget(self.build_version_label)
        self.content_layout.addWidget(self.build_version_input)
        self.content_layout.addWidget(self.edit_button)
        self.content_layout.addWidget(self.build_button)

        # Add the "Add" button - it will be managed by visibility
        # It needs its own layout logic or careful spacer management if we want it centered
        # For now, let's add it directly, visibility will handle it.
        # We'll add spacers specifically when *only* the add button is shown.
        self.content_layout.addWidget(self.add_button)

        # Spacers for centering the 'Add' button when it's alone
        self.left_spacer = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self.right_spacer = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )

        # Connect signals
        self.edit_button.clicked.connect(self.open_edit_dialog)
        self.build_button.clicked.connect(self.trigger_build)
        self.add_button.clicked.connect(self.open_edit_dialog)

        outer_layout.addWidget(self.contrast_frame)

        # Load initial state and set visibility correctly
        self._load_and_display_target()

    def _set_widgets_visibility(self, show_target_details: bool):
        """Helper to show/hide widgets based on target presence."""
        # --- Widgets for existing target ---
        self.target_label.setVisible(show_target_details)
        self.build_version_label.setVisible(show_target_details)  # Show/hide new label
        self.build_version_input.setVisible(show_target_details)
        self.edit_button.setVisible(show_target_details)
        self.build_button.setVisible(show_target_details)
        # The stretch is part of the layout, always present but effective only
        # when buttons are visible and need pushing.

        # --- Widget for adding a new target ---
        self.add_button.setVisible(not show_target_details)

        # --- Manage Spacers for Centering 'Add' Button ---
        # Remove existing spacers first if they are there
        if self.content_layout.itemAt(0) == self.left_spacer:
            self.content_layout.removeItem(self.left_spacer)
        if (
            self.content_layout.itemAt(self.content_layout.count() - 1)
            == self.right_spacer
        ):
            self.content_layout.removeItem(self.right_spacer)

        # Add spacers ONLY if the 'Add' button is the only visible element
        if not show_target_details:
            # Insert spacer at the beginning
            self.content_layout.insertItem(0, self.left_spacer)
            # Add spacer at the end (after the add_button which is now the last widget)
            self.content_layout.addItem(self.right_spacer)

        # Invalidate layout to reflect spacer changes
        self.content_layout.invalidate()
        self.content_layout.activate()

    def _load_and_display_target(self):
        """Fetches the BuildTarget by ID and updates the UI visibility and content."""
        if self._build_target_id is None:
            self._set_widgets_visibility(False)  # Show only Add button centered
            return

        try:
            with session_scope() as session:
                # Re-fetch the target to ensure it's in the current session
                build_target = session.get(BuildTarget, self._build_target_id)

                if build_target:

                    display_text = build_target.__repr__()
                    self.target_label.setText(display_text)
                    self.target_label.setToolTip(
                        f"Currently configured build target:\n{display_text}"
                    )
                    self.build_button.setEnabled(True)
                    self._set_widgets_visibility(True)
                else:
                    logging.info(f"BuildTarget with ID {self._build_target_id} not found.")
                    self._build_target_id = None  # Reset ID if not found
                    self._set_widgets_visibility(False)  # Show only Add button centered
        except Exception as e:
            logging.info(
                f"Error loading BuildTarget ID {self._build_target_id}: {e}",
                exc_info=True,
            )
            self._build_target_id = None  # Reset on error
            self._set_widgets_visibility(False)  # Show only Add button centered

    def open_edit_dialog(self):
        # This function now serves both "Edit" and "Add" clicks
        dialog = BuildTargetSetupDialog(build_target_id=self._build_target_id)
        # Ensure signal connection is robust
        try:
            # Check if already connected (less critical here, but good practice)
            # dialog.build_target_created.disconnect(self.on_new_build_target)
            pass  # Disconnect if needed
        except TypeError:
            pass  # Signal not connected
        dialog.build_target_created.connect(self.on_new_build_target)
        dialog.exec()

    def on_new_build_target(self, new_build_target_id: int):
        logging.info(f"Received new/updated build target ID: {new_build_target_id}")
        self._build_target_id = new_build_target_id
        self._load_and_display_target()  # Refresh UI

    def trigger_build(self):
        if self._build_target_id is None:
            QMessageBox.warning(self, "Error", "No build target selected.")
            return

        # Get build version from the input field
        release_name = self.build_version_input.text().strip()
        if not release_name:
            QMessageBox.warning(
                self,
                "Input Error",
                "Please enter a build version/release name.",
            )
            # Maybe set focus back to the input field
            # self.build_version_input.setFocus()
            return

        # --- Proceed with build logic using 'release_name' ---
        try:
            with session_scope() as session:
                current_build_target = session.get(BuildTarget, self._build_target_id)

                if not current_build_target:
                    QMessageBox.critical(
                        self,
                        "Error",
                        f"Build target with ID {self._build_target_id} not found in database.",
                    )
                    self._load_and_display_target()
                    return

                # Eager load project relationship
                if not current_build_target.project:
                    # This assumes the relationship lazy loading works or is handled
                    # If session.get doesn't load relationships, explicitly query/load it
                    # For simplicity, assuming project is loaded via relationship access:
                    try:
                        _ = (
                            current_build_target.project.name
                        )  # Access attribute to trigger load
                    except AttributeError:
                        # Handle case where project is genuinely None after access attempt
                        QMessageBox.critical(
                            self,
                            "Error",
                            "Associated project data not found for the build target.",
                        )
                        return

                # Get necessary paths and names
                builds_root = current_build_target.project.archive_directory
                source_dir = current_build_target.project.source_dir
                project_name = current_build_target.project.name

                if not all([builds_root, source_dir, project_name]):
                    QMessageBox.critical(
                        self,
                        "Configuration Error",
                        "Project archive directory, source directory, or name is missing.",
                    )
                    return
                
                engine_base_path = current_build_target.unreal_engine_base_path
                if not engine_base_path or not os.path.isdir(engine_base_path):
                    QMessageBox.warning(self, "Configuration Error",
                                        "Unreal Engine base path is not configured or invalid for this specific Build Target.\n\n"
                                        "Please use the 'Edit' button to configure it.")
                    return # Stop the build process
                logging.info(f"Using Unreal Engine Path from Build Target config: {engine_base_path}")

                project_build_dir_root = Path(builds_root) / project_name / release_name

                # Check for existing build and overwrite confirmation
                if project_build_dir_root.exists():
                    response = QMessageBox.question(
                        self,
                        "Build Conflict",
                        f"A build already exists for release:\n{release_name}\n\n"
                        f"Directory:\n{project_build_dir_root}\n\n"
                        "Do you want to proceed and overwrite it?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if response == QMessageBox.StandardButton.No:
                        return

                    try:
                        shutil.rmtree(project_build_dir_root)
                        logging.info(
                            f"Removed existing build directory: {project_build_dir_root}"
                        )
                    except Exception as e:
                        logging.info(
                            f"Failed to delete existing build directory: {e}",
                            exc_info=True,
                        )
                        QMessageBox.critical(
                            self,
                            "Cleanup Error",
                            f"Failed to delete existing build directory:\n{str(e)}",
                        )
                        return

                # Prepare builder arguments
                try:
                    target_platform_val = current_build_target.target_platform.value
                    build_type_val = current_build_target.build_type.value
                    optimize_steam = current_build_target.optimize_for_steam
                except AttributeError as e:
                    logging.info(f"Missing build target attribute: {e}", exc_info=True)
                    QMessageBox.critical(
                        self,
                        "Configuration Error",
                        f"Build target is missing required information (e.g., platform, type): {e}",
                    )
                    return

                # Create and run the builder
                try:
                    unreal_builder = UnrealBuilder(
                        source_dir=source_dir,
                        # Make engine path configurable via SettingsDialog later
                        engine_path=engine_base_path,
                        target_platform=target_platform_val,
                        target_config=build_type_val,
                        output_dir=project_build_dir_root,
                        clean=False,  # Confirm if 'clean' should be an option
                        valve_package_pad=optimize_steam,
                    )
                # Specific error handling for UnrealBuilder initialization
                except ProjectFileNotFoundError as e:
                    QMessageBox.critical(
                        self, "Project File Error", f"Project file not found: {str(e)}"
                    )
                    return
                except EngineVersionError as e:
                    QMessageBox.critical(
                        self,
                        "Engine Version Error",
                        f"Could not determine Unreal Engine version: {str(e)}",
                    )
                    return
                except UnrealEngineNotInstalledError as e:
                    QMessageBox.critical(
                        self,
                        "Unreal Engine Not Found",
                        f"Unreal Engine not found. Please check configuration.\nError: {str(e)}",
                    )
                    return
                except Exception as e:  # Catch other builder init errors
                    logging.info(
                        f"Unexpected error creating UnrealBuilder: {e}", exc_info=True
                    )
                    QMessageBox.critical(
                        self,
                        "Build Setup Error",
                        f"Failed to initialize the builder:\n{str(e)}",
                    )
                    return

                # Show the build progress dialog
                logging.info(f"Starting build dialog for release '{release_name}'...")
                dialog = BuildWindowDialog(unreal_builder, parent=self)
                try:
                    # dialog.build_ready_signal.disconnect(self.build_ready_signal) # If needed
                    pass
                except TypeError:
                    pass
                dialog.build_ready_signal.connect(
                    self.build_ready_signal
                )  # Connect signal from build dialog
                dialog.exec()  # Show modal build dialog

        except Exception as e:
            # Catch errors during session management or top-level logic
            logging.info(f"Error during trigger_build: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"An unexpected error occurred during the build process: {e}",
            )
