from abc import ABC, abstractmethod

class BasePublisher(ABC):
    @abstractmethod
    def publish(self, build_path: str, parent=None):
        """Execute the publishing process."""
        pass