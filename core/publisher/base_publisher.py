import os
import sys
import json
from abc import ABC, abstractmethod
from PyQt6.QtWidgets import QDialog

from exceptions import InvalidConfigurationError


class BasePublisher(ABC):
    store_name = None
    
    def __init__(self, build_path, config_path):
        self.build_path = build_path

    @abstractmethod
    def publish(self, parent=None):
        """Execute the publishing process."""
        pass