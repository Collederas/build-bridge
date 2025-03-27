import pytest
from vcs.p4client import P4Client

@pytest.fixture(scope="module")
def p4_client():
    """
    Fixture to create a P4 client connected to a test Perforce server.
    Uses environment variables or a test configuration file.
    """
    client = P4Client(config_path="tests/tesT_vcsconfig.json")
    
    try:
        client.ensure_connected()
        yield client
        client.close_connection()
    except Exception as e:
        pytest.fail(f"Could not connect to Perforce server: {e}")