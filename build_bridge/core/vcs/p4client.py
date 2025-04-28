import os
from typing import List, Optional


from build_bridge.core.vcs.vcsbase import VCSClient
from P4 import P4, P4Exception

from build_bridge.models import PerforceConfig


class P4Client(VCSClient):

    # We don't *need* a config because p4 can read env variables and use those
    def __init__(self, config: PerforceConfig = None):
        super().__init__()
        self.p4 = P4()

        self.config = config
        self.workspace_root = self.get_workspace_root()
        self.p4.exception_level = (
            1  # File(s) up-to-date is a warning - no exception raised
        )

    @property
    def is_connected(self) -> bool:
        return self.p4.connected()

    def _connect(self) -> None:
        if not self.is_connected:
            logging.info("p4 not connected. Attempting connection now.")
            if self.config:
                self.p4.port = self.config.server_address
                self.p4.user = self.config.user
                self.p4.password = self.config.p4password
                self.p4.client = self.config.client

            try:
                self.p4.connect()
                if self.p4.password:  # Only run login if a password is set
                    self.p4.run_login()
                    logging.info(f"p4 connection established. Logged in as {self.p4.user}")
            except P4Exception as e:
                logging.info(e)
                raise ConnectionError(f"P4 connection error: {e}")
        else:
            logging.info("Already connected")

    def _disconnect(self):
        self.p4.disconnect()

    def get_workspace_root(self):
        try:
            self.ensure_connected()
            info = self.p4.run("info")[0]
            return info.get("clientRoot")
        except P4Exception as e:
            raise RuntimeError(
                f"Could not retrieve workspace root: {str(e)}\n"
                "Ensure your Perforce client is properly configured."
            )

    def get_branches(self, stream_filter: Optional[str] = "Type=release") -> List[str]:
        """
        Returns Perforce streams matching server-side filter criteria, defaulting to release streams.

        Args:
            stream_filter: P4 filter expression using stream spec fields.
                Defaults to "Type=release" to fetch release streams.
                Example: "Type=release & Parent=//Streams/Main"
        """
        try:
            self.ensure_connected()
            command_args = ["streams"]
            if stream_filter:
                command_args.extend(["-F", stream_filter])

            streams = self.p4.run(*command_args)
            stream_paths = [s["Stream"] for s in streams]
            if not stream_paths:
                return []  # Empty list instead of raising an error
            return stream_paths
        except P4Exception as e:
            raise RuntimeError(
                f"Failed to fetch release branches: {str(e)}\n"
                "Check your Perforce connection and stream filter settings."
            )

    def switch_to_ref(self, ref: str) -> None:
        """
        Switches to a specific stream using 'p4 switch'.
        For non-stream workflows, uses 'p4 sync' on the branch path.
        """
        try:
            self.ensure_connected()
            opened_files = self.p4.run("opened")
            if opened_files:
                raise RuntimeError(
                    "You have pending changes in your workspace.\n"
                    "Please shelve or submit them before switching branches."
                )

            os.chdir(self.get_workspace_root())
            self.p4.run("switch", ref)
            self.p4.run_sync()
        except P4Exception as e:
            raise RuntimeError(f"Failed to switch to stream '{ref}': {str(e)}")
