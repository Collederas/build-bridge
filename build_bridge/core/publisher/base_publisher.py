from abc import ABC, abstractmethod

from build_bridge.core.publisher.upload_spec import UploadSpec


class BasePublisher(ABC):
    @abstractmethod
    def validate_publish_profile(self):
        """Validate store-specific conf potentially misconfigured
        or missing from the given profile."""

    @abstractmethod
    def prepare(self, content_dir: str, version: str = "") -> UploadSpec:
        """Build the UploadSpec for this publish. Does not start any process."""
