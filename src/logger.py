import os
import logging
from logging.handlers import RotatingFileHandler

_LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | %(name)s"
    " | context: %(context)s | %(message)s | state: %(state)s"
)
_LOG_FORMAT_SIMPLE = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

_ROOT_LOGGER_NAME = "klute_timer"
_initialized = False


class _ContextFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "context"):
            record.context = "none"
        if not hasattr(record, "state"):
            record.state = "none"
        return True


def setup_logger(
    log_dir: str = "logs",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 3,
    level: int = logging.DEBUG,
) -> None:
    global _initialized
    if _initialized:
        return

    os.makedirs(log_dir, exist_ok=True)

    root_logger = logging.getLogger(_ROOT_LOGGER_NAME)
    root_logger.setLevel(level)

    context_filter = _ContextFilter()

    log_path = os.path.join(log_dir, "klute-timer.log")
    file_handler = RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S"))
    file_handler.addFilter(context_filter)

    root_logger.addHandler(file_handler)
    _initialized = True


def get_logger(module_name: str) -> logging.Logger:
    return logging.getLogger(f"{_ROOT_LOGGER_NAME}.{module_name}")


def _reset_logger() -> None:
    """Reset the logger state for testing purposes."""
    global _initialized
    root_logger = logging.getLogger(_ROOT_LOGGER_NAME)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()
    _initialized = False
