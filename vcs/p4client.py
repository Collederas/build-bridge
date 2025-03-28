import os
import re
from typing import List, Optional, Dict, Tuple
from vcs.vcsbase import VCSClient

from P4 import P4, P4Exception


class P4Client(VCSClient):
    def __init__(self, config: Optional[str] = None):
        super().__init__(config)
        self.p4 = P4()
        self.workspace_root = self.get_workspace_root()
        self.p4.exception_level = (
            1  # File(s) up-to-date is a warning - no exception raised
        )

    @property
    def is_connected(self) -> bool:
        return self.p4.connected()

    def _connect(self) -> None:
        # Defaults to use p4 env variables. If config_override exists, it will use that.
        if config_override := self.config.get("perforce").get("config_override"):
            self.p4.port = config_override["p4port"]
            self.p4.user = config_override["p4user"]
            self.p4.password = config_override["p4password"]
            self.p4.client = config_override["p4client"]
        try:
            self.p4.connect()
            self.p4.run_login()
        except P4Exception as e:
            raise ConnectionError(f"P4 connection error: {e}")

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

    def get_project_path(self, stream: str):
        try:
            if not self.workspace_root:
                self.get_workspace_root()

            where_output = self.p4.run("where", f"{stream}/...")
            if not where_output or not isinstance(where_output, list):
                raise RuntimeError(
                    f"Depot path '{stream}' could not be mapped to a local path."
                )

            local_path = where_output[0].get("path")
            if not local_path:
                raise RuntimeError(f"No local path found for depot stream '{stream}'.")

            local_base_dir = os.path.normpath(local_path.rsplit("\\...", 1)[0])
            
            #TODO: remove hardcoded, make configurable
            return os.path.join(local_base_dir, "AtmosProject")

        except P4Exception as e:
            raise RuntimeError(f"Perforce error while mapping project path: {str(e)}")

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

    @staticmethod
    def test_connection(
        address: str, user: str, password: str
    ) -> Tuple[str, Optional[str]]:
        p4 = P4()
        p4.port = address
        p4.user = user
        p4.password = password
        try:
            p4.connect()
            p4.run_login()
            if p4.connected():
                return "success", None
            return "error", "Connection failed: Unable to establish connection."
        except P4Exception as e:
            return "error", str(e)
        finally:
            if p4.connected():
                p4.disconnect()
