import pytest
from src.logger import _reset_logger


@pytest.fixture(autouse=True)
def reset_logger_after_each_test():
    """Reset the logger state before each test to prevent interference."""
    _reset_logger()
    yield
    _reset_logger()
