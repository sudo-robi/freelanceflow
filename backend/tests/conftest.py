import pytest

from app.ratelimit import reset_rate_limits


@pytest.fixture(autouse=True)
def isolated_rate_limits():
    """Each test starts and ends with empty rate-limit windows."""
    reset_rate_limits()
    yield
    reset_rate_limits()
