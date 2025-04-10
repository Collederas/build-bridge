from abc import ABC, abstractmethod

from build_bridge.models import PublishProfile


class BasePublisher(ABC):
    # This was born with the idea of being a nice interface but it's
    # almost useless. Probably worth removing it.

    @abstractmethod
    def validate_publish_profile(self, publish_profile):
        """Validate store-specific conf potentially misconfigured
        or missing from the given profile."""


    @abstractmethod
    def publish(self, parent=None):
        """Execute the publishing process."""
