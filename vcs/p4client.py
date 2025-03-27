import re
from typing import List, Optional, Dict, Tuple
from vcs.vcsbase import VCSClient

from P4 import P4, P4Exception


class P4Client(VCSClient):
    def __init__(self, config: Optional[dict] = None, config_path: Optional[str] = None):
            super().__init__(config_path)
            self.p4 = P4()
            self.config = config or {}
            self.vcs_config = self.config.get("perforce", {})

    @property
    def is_connected(self) -> bool:
        return self.p4.connected()

    def _get_vcs_name(self) -> str:
        return "perforce"  # Matches the JSON key

    def _connect(self) -> None:
        # Only override with config if use_config is True and config exists
        if self.use_config and (config_override := self.config.get("config_override")):
            self.p4.port = config_override["p4port"]
            self.p4.user = config_override["p4user"]
            self.p4.password = config_override["p4password"]
            self.p4.client = config_override["p4client"]
        try:
            print(f"Connecting with port: {self.p4.port}")  # Debug
            self.p4.connect()
            self.p4.run_login()
        except P4Exception as e:
            raise ConnectionError(f"P4 connection error: {e}")

    def _disconnect(self):
        self.p4.disconnect()

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
        port: str, user: str, password: str, client: str
    ) -> Tuple[str, Optional[str]]:
        p4 = P4()
        p4.port = port
        p4.user = user
        p4.password = password
        p4.client = client
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
