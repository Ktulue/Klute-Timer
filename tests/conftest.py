import pytest

from src.logger import _reset_logger
from src.paths import ENV_DATA_DIR


@pytest.fixture(autouse=True)
def reset_logger_after_each_test():
    """Reset the logger state before each test to prevent interference."""
    _reset_logger()
    yield
    _reset_logger()


@pytest.fixture(autouse=True)
def isolate_user_data(tmp_path, monkeypatch):
    r"""Keep the suite away from the real %APPDATA%\KluteTimer.

    User data now resolves to a fixed machine-wide location, so a test that
    forgot to redirect it would read and overwrite the developer's own presets.
    Tests that care about the resolution rules override this themselves.
    """
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path / "user-data"))
