import keyring
import pytest
import json
from vcs.p4client import P4Client


@pytest.fixture(scope="module")
def p4_client():
    """
    Fixture to create a P4 client connected to a test Perforce server.
    Uses environment variables or a test configuration file.
    """
    config_path = "tests/tesT_vcsconfig.json"

    with open(config_path, "r") as f:
        config = json.load(f)

    password = keyring.get_password(
        "BuildBridge", config["perforce"]["config_override"]["p4user"]
    )
    config["perforce"]["config_override"]["p4password"] = password
    client = P4Client(config)

    try:
        client.ensure_connected()
        yield client
        client.close_connection()
    except Exception as e:
        pytest.fail(f"Could not connect to Perforce server: {e}")
