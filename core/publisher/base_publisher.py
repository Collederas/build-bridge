import os
import sys
import json
from abc import ABC, abstractmethod
from PyQt6.QtWidgets import QDialog

from exceptions import InvalidConfigurationError


class BasePublisher(ABC):    
    @abstractmethod
    def publish(self, parent=None):
        """Execute the publishing process."""
        pass