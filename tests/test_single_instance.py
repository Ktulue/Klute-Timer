import ctypes
import uuid
from ctypes import wintypes

from src import single_instance

SYNCHRONIZE = 0x00100000

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_open_mutex = _kernel32.OpenMutexW
_open_mutex.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
_open_mutex.restype = wintypes.HANDLE
_close_handle = _kernel32.CloseHandle
_close_handle.argtypes = [wintypes.HANDLE]
_close_handle.restype = wintypes.BOOL


def _mutex_exists(name: str) -> bool:
    handle = _open_mutex(SYNCHRONIZE, False, name)
    if handle:
        _close_handle(handle)
        return True
    return False


def _unique_name() -> str:
    return f"KluteTimer-Test-{uuid.uuid4()}"


def test_mutex_is_visible_while_held():
    name = _unique_name()
    assert not _mutex_exists(name)

    handle = single_instance.hold_app_mutex(name)

    assert handle
    assert _mutex_exists(name)


def test_create_failure_returns_none_without_raising(monkeypatch):
    monkeypatch.setattr(single_instance, "_create_mutex", lambda *args: 0)
    assert single_instance.hold_app_mutex(_unique_name()) is None


def test_create_exception_returns_none_without_raising(monkeypatch):
    def boom(*args):
        raise OSError("access denied")

    monkeypatch.setattr(single_instance, "_create_mutex", boom)
    assert single_instance.hold_app_mutex(_unique_name()) is None
