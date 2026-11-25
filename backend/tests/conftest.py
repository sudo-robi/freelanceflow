import pytest

from app.ratelimit import reset_rate_limits
from app.stellar import TESTNET_PASSPHRASE


@pytest.fixture(autouse=True)
def isolated_rate_limits():
    """Each test starts and ends with empty rate-limit windows."""
    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.fixture(autouse=True)
def controlled_network_passphrase(monkeypatch):
    """Automated tests must not depend on the live Soroban RPC for every confirmation."""
    async def testnet_passphrase():
        return TESTNET_PASSPHRASE

    monkeypatch.setattr("app.main.get_network_passphrase", testnet_passphrase)
