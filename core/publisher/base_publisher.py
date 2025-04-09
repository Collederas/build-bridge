from abc import ABC, abstractmethod


class BasePublisher(ABC):
    # This was born with the idea of being a nice interface but it's
    # almost useless. Probably worth removing it.
    @abstractmethod
    def publish(self, parent=None):
        """Execute the publishing process."""
