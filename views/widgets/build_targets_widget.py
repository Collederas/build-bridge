from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QComboBox,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
    QVBoxLayout,
    QFrame,
)

from core.vcs.p4client import P4Client
from database import session_scope
from models import BuildTarget
from views.dialogs.build_target_setup_dialog import BuildTargetSetupDialog


class BuildTargetListWidget(QWidget):
    """Lists the available Build Targets"""

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.vcs_client = parent.vcs_client

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        # Contrast frame
        contrast_frame = QFrame()
        contrast_frame.setObjectName("contrastFrame")
        contrast_frame.setFrameShape(QFrame.Shape.StyledPanel)

        # Scoped style just to this frame
        contrast_frame.setStyleSheet(
            """
            QFrame#contrastFrame {
                background-color: #f9f9f9;
                border: 1px solid #ccc;
                border-radius: 6px;
                padding: 10px;
            }
        """
        )

        layout = QHBoxLayout(contrast_frame)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        self.label = QLabel("Project Name - Platform - Shipping")

        # Branches
        self.branches_combo = QComboBox()
        self.branches_combo.addItems(["release/0.2", "release/0.3"])

        self.publish_button = QPushButton("Build")
        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self.open_edit_dialog)

        layout.addWidget(self.label)
        layout.addWidget(self.branches_combo)
        layout.addWidget(self.edit_button)
        layout.addWidget(self.publish_button)

        outer_layout.addWidget(contrast_frame)

        self.refresh_branches()

    def refresh_branches(self):
        if not self.vcs_client:
            return

        try:
            self.branches_combo.clear()
            branches = self.vcs_client.get_branches()
            if not branches:
                self.branches_combo.addItem("No release branches found.")
            else:
                self.branches_combo.addItems(branches)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load branches: {str(e)}")

    def open_edit_dialog(self):
        # TODO: this is a hack until multiple build targets are supported.
        # right now the app only supports one.
        with session_scope() as session:
            build_target = session.query(BuildTarget).first()

            # If a target exists use that. Else it will be created at the end
            # of the dialog, when accepted.
            build_target_id = build_target.id if build_target else None
            dialog = BuildTargetSetupDialog(build_target_id=build_target_id)

        dialog.exec()
