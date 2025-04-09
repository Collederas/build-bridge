
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTabWidget,
    QLabel,
    QPushButton,
    QMessageBox,
    QFrame,
)

from database import SessionFactory
from views.dialogs.steam_publish_profile_dialog import SteamPublishProfileWidget
from views.dialogs.itch_publish_profile_dialog import ItchPublishProfileWidget


class PlatformPublishDialog(QDialog):
    """
    A dialog that shows either Steam or Itch.io publish profile based on the platform argument.
    Can also show both in a tabbed interface when no specific platform is specified.
    """
    def __init__(self, build_id, platform=None, parent=None):
        """
        Initialize the platform-specific publish dialog.
        
        Args:
            session: Database session
            build_id: The build ID for the profile
            platform: "steam", "itch", or None (which shows both tabs)
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.build_id = build_id
        self.platform = platform
        self.steam_widget = None
        self.itch_widget = None
        self.session = SessionFactory()
        
        # Set window properties
        self.setWindowTitle(f"Publish Profile - {build_id}")
        self.setMinimumWidth(650)
        self.setMinimumHeight(500)
        
        self._init_ui()
        
    def _init_ui(self):
        """Initialize the user interface based on the requested platform."""
        # Main layout for this container dialog
        main_layout = QVBoxLayout(self)
        
        # Create different layouts based on platform
        if self.platform is None:
            # Show both platforms in tabs
            self._create_tabbed_interface(main_layout)
        elif self.platform.lower() == "steam":
            # Show only Steam
            self._create_steam_dialog(main_layout)
        elif self.platform.lower() == "itch":
            # Show only Itch
            self._create_itch_dialog(main_layout)
        else:
            # Invalid platform specified
            error_label = QLabel(f"Invalid platform specified: {self.platform}")
            error_label.setStyleSheet("color: red; font-weight: bold;")
            main_layout.addWidget(error_label)
            
            close_button = QPushButton("Close")
            close_button.clicked.connect(self.reject)
            main_layout.addWidget(close_button)
            
            QMessageBox.warning(
                self, 
                "Invalid Platform", 
                f"Invalid platform '{self.platform}'. Valid options are 'steam' or 'itch'."
            )
        
        self.setLayout(main_layout)
    
    def _create_tabbed_interface(self, parent_layout):
        """Create a tabbed interface showing both Steam and Itch platforms."""
        tab_widget = QTabWidget()
        
        # Steam tab
        steam_tab = QFrame()
        steam_layout = QVBoxLayout(steam_tab)
        self.steam_widget = SteamPublishProfileWidget(session=self.session, build_id=self.build_id, parent=self)
        steam_layout.addWidget(self.steam_widget)
        
        # Itch tab
        itch_tab = QFrame()
        itch_layout = QVBoxLayout(itch_tab)
        self.itch_widget = ItchPublishProfileWidget(session=self.session, build_id=self.build_id, parent=self)
        itch_layout.addWidget(self.itch_widget)
        
        # Add tabs to the widget
        tab_widget.addTab(steam_tab, "Steam")
        tab_widget.addTab(itch_tab, "Itch.io")
        
        parent_layout.addWidget(tab_widget)
        
        # Connect the tab changes to handle validation when switching
        tab_widget.currentChanged.connect(self._on_tab_changed)
        
        # Add save and cancel buttons at the bottom
        button_layout = self._create_button_layout()
        parent_layout.addLayout(button_layout)
    
    def _create_steam_dialog(self, parent_layout):
        """Create a Steam-only dialog."""
        self.steam_widget = SteamPublishProfileWidget(self.session, self.build_id, self)
        parent_layout.addWidget(self.steam_widget)
        
        # The SteamPublishProfileDialog already has its own buttons
        # Override the default accept/reject to use this dialog
        self.steam_widget.accepted.connect(self.accept)
        self.steam_widget.rejected.connect(self.reject)
    
    def _create_itch_dialog(self, parent_layout):
        """Create an Itch-only dialog."""
        self.itch_widget = ItchPublishProfileWidget(self.session, self.build_id, self)
        parent_layout.addWidget(self.itch_widget)
        
        # The ItchPublishProfileDialog already has its own buttons
        # Override the default accept/reject to use this dialog
        self.itch_widget.accepted.connect(self.accept)
        self.itch_widget.rejected.connect(self.reject)
    
    def _create_button_layout(self):
        """Create save and cancel buttons for the tabbed interface."""
        from PyQt6.QtWidgets import QHBoxLayout
        
        button_layout = QHBoxLayout()
        
        save_button = QPushButton("Save && Close")
        save_button.clicked.connect(self._save_active_profile)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        
        return button_layout
    
    def _on_tab_changed(self, index):
        """Handle tab change events, potentially validating any unsaved changes."""
        # In the future, we could add validation before switching tabs
        # For now, just a simple indicator for debugging
        tab_name = "Steam" if index == 0 else "Itch.io"
        print(f"Switched to {tab_name} tab")
    
    def _save_active_profile(self):
        """Save the currently active profile based on the selected tab."""
        tab_widget = self.findChild(QTabWidget)
        if tab_widget:
            current_index = tab_widget.currentIndex()
            if current_index == 0 and self.steam_widget:
                # Save Steam profile
                self.steam_widget.save_profile()
            elif current_index == 1 and self.itch_widget:
                # Save Itch profile
                self.itch_widget.save_profile()
        else:
            # This shouldn't happen in tabbed mode
            QMessageBox.warning(self, "Error", "Cannot determine which profile to save.")
        self.accept()
    
    def accept(self):
        self.session.close()

        """Override accept to ensure we handle our own accept logic."""
        super().accept()
    
    def reject(self):
        """Override reject to ensure we handle our own reject logic."""
        self.session.rollback()
        self.session.close()
        super().reject()


