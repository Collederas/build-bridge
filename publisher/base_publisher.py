import os
import sys
import json
import logging
from abc import ABC, abstractmethod
from PyQt6.QtWidgets import QDialog

logger = logging.getLogger(__name__)

class BasePublisher(ABC):
    store_name = None

    @abstractmethod
    def publish(self, parent=None):
        """Execute the publishing process."""
        pass