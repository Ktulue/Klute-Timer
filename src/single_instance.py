"""Lets the installer see that Klute Timer is running.

The app holds a named mutex for as long as it runs. Inno Setup's AppMutex
directive checks for that name, so install, upgrade and uninstall stop and ask
the user to close the app rather than replacing files under a live timer. It
does not stop a second copy of the app launching.

installer/KluteTimer.iss repeats APP_MUTEX_NAME; tests/test_packaging.py keeps
the two in step.
"""
import ctypes
from ctypes import wintypes
from typing import Optional

from src.logger import get_logger

APP_MUTEX_NAME = "KluteTimer-AppMutex"

log = get_logger("single_instance")

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_create_mutex = _kernel32.CreateMutexW
_create_mutex.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
_create_mutex.restype = wintypes.HANDLE

# Referenced for the life of the process. Windows closes the handles, and so
# releases the name, when the process exits.
_held_handles: list[int] = []


def hold_app_mutex(name: str = APP_MUTEX_NAME) -> Optional[int]:
    """Create the named mutex and keep it. Returns the handle, or None on failure.

    Never raises: failing here only means the installer cannot detect the
    running app, which must not stop the app itself from launching.
    """
    try:
        handle = _create_mutex(None, False, name)
    except Exception as e:
        log.warning(
            f"could not create app mutex: {e}",
            extra={"context": "startup", "state": f"name={name}"},
        )
        return None

    if not handle:
        log.warning(
            f"could not create app mutex: WinError {ctypes.get_last_error()}",
            extra={"context": "startup", "state": f"name={name}"},
        )
        return None

    _held_handles.append(handle)
    return handle
