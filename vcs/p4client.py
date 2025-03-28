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
        """
        Retrieves the current Perforce workspace root directory.
        """
        try:
            self.ensure_connected()
            info = self.p4.run("info")[0]
            return info.get("Client root")  # Extracts the workspace root
        except P4Exception:
            raise RuntimeError("Failed to retrieve Perforce workspace root.")
        
    def get_project_path(self, stream: str):
        try:
            if not self.workspace_root:
                self.get_workspace_root()

            # Map depot path to local path
            where_output = self.p4.run("where", f"{stream}/...")
            if not where_output or not isinstance(where_output, list):
                raise RuntimeError(f"Could not map depot path {stream} to local path.")

            # Extract the first valid mapping
            local_path = where_output[0].get("path")
            if not local_path:
                raise RuntimeError(f"Could not determine local path for {stream}.")

            # Normalize and extract the base directory
            local_base_dir = os.path.normpath(local_path.rsplit("/...", 1)[0])

            # Search for a .uproject file
            for root, _, files in os.walk(local_base_dir):
                for file in files:
                    if file.endswith(".uproject"):
                        return os.path.join(root, file)

            raise RuntimeError(f"No .uproject file found in {local_base_dir}.")

        except P4Exception as e:
            raise RuntimeError(f"Failed to determine local project path: {str(e)}")

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

            # Apply server-side filtering (default or custom)
            if stream_filter:
                command_args.extend(["-F", stream_filter])

            streams = self.p4.run(*command_args)
            stream_paths = [s["Stream"] for s in streams]
            return stream_paths

        except P4Exception as e:
            raise RuntimeError(f"Failed to get streams: {str(e)}")

    def switch_to_ref(self, ref: str) -> None:
        """
        Switches to a specific stream using 'p4 switch'.
        For non-stream workflows, uses 'p4 sync' on the branch path.
        """
        try:
            self.ensure_connected()
            opened_files = self.p4.run("opened")
            if opened_files:
                print("⚠️ WARNING: You have pending changes!")
                print("Please shelve or submit them before switching streams.")
                return

            # Change to workspace root before executing p4 commands
            original_dir = os.getcwd()
            os.chdir(self.workspace_root)

            print(f"🔄 Switching to stream: {ref}")
            self.p4.run("switch", ref)

            # Force sync to ensure correct files
            print("🔃 Syncing files to match the new stream...")
            self.p4.run("sync", "-f")

            print("✅ Stream switch complete!")

        except P4Exception as e:
            raise RuntimeError(f"Failed to switch to {ref}: {str(e)}")

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
