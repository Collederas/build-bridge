from abc import ABC, abstractmethod

class BasePublisher(ABC):
    @abstractmethod
    def publish(self, parent=None):
        """Execute the publishing process."""
        pass