from turtle import pu
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTabWidget,
    QLabel,
    QPushButton,
    QMessageBox,
    QFrame,
)

from PyQt6.QtCore import pyqtSignal

from build_bridge.models import PublishProfile, StoreEnum
from build_bridge.utils.paths import get_resource_path
from build_bridge.views.widgets.publish_profile_edit_widget_steam import (
    SteamPublishProfileWidget,
)
from build_bridge.views.widgets.publish_profile_edit_widget_itch import (
    ItchPublishProfileWidget,
)
from PyQt6.QtGui import QIcon


class PublishProfileDialog(QDialog):
    """
    A dialog that shows either Steam or Itch.io publish profile based on the platform argument.
    """

    profile_changed_signal = pyqtSignal()

    def __init__(self, session, publish_profile: PublishProfile, parent=None):
        """
        Initialize the platform-specific publish dialog.

        Args:
            session: Database session
            build_id: The build ID for the profile
            platform: "steam", "itch", or None (which shows both tabs)
            parent: Parent widget
        """
        super().__init__(parent)

        self.steam_widget = None
        self.itch_widget = None
        self.publish_profile = publish_profile
        self.session = session

        # Set window properties
        self.setWindowTitle(
            f"Publish Profile for build v.- {self.publish_profile.build_id}"
        )

        self.setMinimumWidth(650)
        self.setMinimumHeight(500)
        icon_path = str(get_resource_path("icons/buildbridge.ico"))
        self.setWindowIcon(QIcon(icon_path))

        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface based on the requested platform."""
        # Main layout for this container dialog
        main_layout = QVBoxLayout(self)
        store_type = self.publish_profile.store_type

        if store_type == StoreEnum.steam:
            # Show only Steam
            self._create_steam_dialog(main_layout)
        elif store_type == StoreEnum.itch:
            # Show only Itch
            self._create_itch_dialog(main_layout)
        else:
            # Invalid platform specified
            error_label = QLabel(f"Invalid platform specified: {store_type}")
            error_label.setStyleSheet("color: red; font-weight: bold;")
            main_layout.addWidget(error_label)

            close_button = QPushButton("Close")
            close_button.clicked.connect(self.reject)
            main_layout.addWidget(close_button)

            QMessageBox.warning(
                self,
                "Invalid Platform",
                f"Invalid platform '{store_type}'. Valid options are 'steam' or 'itch'.",
            )

        self.setLayout(main_layout)

    def _create_steam_dialog(self, parent_layout):
        """Create a Steam-only dialog."""
        self.steam_widget = SteamPublishProfileWidget(
            publish_profile=self.publish_profile, session=self.session, parent=self
        )
        parent_layout.addWidget(self.steam_widget)
        self.steam_widget.profile_saved_signal.connect(self.new_profile_created)

    def _create_itch_dialog(self, parent_layout):
        """Create an Itch-only dialog."""
        self.itch_widget = ItchPublishProfileWidget(
            publish_profile=self.publish_profile, session=self.session, parent=self
        )
        parent_layout.addWidget(self.itch_widget)
        self.itch_widget.profile_saved_signal.connect(self.new_profile_created)

    def new_profile_created(self):
        self.profile_changed_signal.emit()
        self.close()

    def _create_button_layout(self):
        from PyQt6.QtWidgets import QHBoxLayout

        button_layout = QHBoxLayout()

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(cancel_button)

        return button_layout

    def reject(self):
        self.session.rollback()
        return super().reject()