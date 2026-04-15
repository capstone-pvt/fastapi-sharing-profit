"""Fish-test-specific fixtures."""
import pytest


@pytest.fixture(scope="session")
def auth_headers(broker_headers):
    """Alias for broker_headers — brokers have fish:analyze permission."""
    return broker_headers
