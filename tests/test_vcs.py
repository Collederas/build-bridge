import pytest
from unittest.mock import MagicMock, patch


class TestP4Client:
    def test_real_connection(self, p4_client):
        """
        Verify basic connection works
        """
        assert p4_client.is_connected, "P4 client should be connected"

    def test_retrieve_release_branches(self, p4_client):
        """
        Retrieve actual release branches from the server
        """
        try:
            release_branches = p4_client.get_branches()
            
            assert isinstance(release_branches, list), "Should return a list of branches"
            
            for branch in release_branches:
                assert branch.startswith("//"), "Branch paths should start with //"
                assert "release" in branch.lower(), "Branches should be release-type"
        
        except Exception as e:
            pytest.fail(f"Failed to retrieve release branches: {e}")

    def test_switch_to_branch(self, p4_client):
        """
        Test switching to a release branch
        Requires at least one release branch to exist
        """
        release_branches = p4_client.get_branches()
        
        if not release_branches:
            pytest.skip("No release branches found to test switching")
        
        try:
            # Try switching to the first release branch
            p4_client.switch_to_ref(release_branches[0])
        except Exception as e:
            pytest.fail(f"Failed to switch to branch {release_branches[0]}: {e}")