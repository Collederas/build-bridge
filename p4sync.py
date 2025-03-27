import json
from vcsmanager import VCSManager
from P4 import P4, P4Exception


class P4Manager(VCSManager):
    def load_config(self):

        p4 = P4()
        p4.port = self.config["p4_host"]
        p4.user = self.config["p4_user"]
        p4.password = self.config["p4_password"]
        p4.client = self.config["p4_client"]

        try:
            p4.connect()
            p4.run("sync")  # Sync the repo to latest version
            branches = p4.run("branches")  # Fetch branches
            return [branch["name"] for branch in branches]
        except P4Exception as e:
            self.update_log(f"Error syncing Perforce: {e}")
            return []
        finally:
            p4.disconnect()

    def sync_repo():
        p4 = P4()
        p4.connect()

        try:
            p4.run("sync")
            branches = p4.run("branches")  # Get list of branches
            return [branch["name"] for branch in branches]
        except P4Exception as e:
            return f"Error syncing Perforce: {e}"

        finally:
            p4.disconnect()
