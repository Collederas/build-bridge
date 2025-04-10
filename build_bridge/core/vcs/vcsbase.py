from contextlib import contextmanager
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Tuple


class MissingConfigException(Exception):
    """Missing configuration"""
    pass

@contextmanager
def vcs_session(config_path="vcsconfig.json"):
    client = VCSClient(config_path)
    try:
        yield client
    finally:
        client.close()


class VCSClient(ABC):
    """Base class to abstract connection to different VCS."""


    @abstractmethod
    def get_branches(self, pattern: Optional[str] = None) -> List[str]:
        """Return branches/tags/streams matching a glob/regex pattern."""
        pass

    @abstractmethod
    def switch_to_ref(self, ref: str) -> None:
        """Switch to a branch/tag/stream (e.g., `git checkout`, `p4 switch`)."""
        pass

    @abstractmethod
    def _connect(self) -> None:
        """VCS-specific connection setup."""
        pass

    @abstractmethod
    def _disconnect(self) -> None:
        """VCS-specific connection closing logic."""
        pass

    @property
    @abstractmethod
    def is_connected(self):
        pass

    def ensure_connected(self) -> None:
        if not self.is_connected:
            try:
                self._connect()
            except Exception as e:
                raise ConnectionError(f"Connection failed: {e}") from e

    def close_connection(self) -> None:
        if not self.is_connected:
            return
        self._disconnect()
