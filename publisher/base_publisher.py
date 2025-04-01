import os
import sys
import json
import logging
from abc import ABC, abstractmethod
from PyQt6.QtWidgets import QDialog

logger = logging.getLogger(__name__)

class BasePublisher(ABC):
    store_name = None
    
    def __init__(self, build_path, config_path):
        self.build_path = build_path
        # this is the directory that will house the config
        # files required by the store
        self.store_config_dir = os.path.join(self.build_path, self.store_name)
        self.config_path = self._get_config_path(config_path)
        self.config = self.load_config()

    def _get_config_path(self, config_path):
        """Handle file paths for both dev and packaged environments."""
        if getattr(sys, 'frozen', False):  # Running as packaged executable
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(__file__)
        return os.path.join(base_path, config_path)

    def load_config(self):
        """Load configuration from JSON file."""
        config = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    config = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load config from {self.config_path}: {str(e)}")
        return config

    def save_config(self, config):
        """Save configuration to JSON file."""
        try:
            with open(self.config_path, "w") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save config to {self.config_path}: {str(e)}")

    @abstractmethod
    def configure(self, parent=None):
        """Show configuration dialog and return updated config."""
        pass

    @abstractmethod
    def publish(self, parent=None):
        """Execute the publishing process."""
        pass