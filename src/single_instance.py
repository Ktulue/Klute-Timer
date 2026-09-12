"""Lets the installer see that Klute Timer is running.

The app holds a named mutex for as long as it runs. Inno Setup's AppMutex
directive checks for that name, so install, upgrade and uninstall stop and ask
the user to close the app rather than replacing files under a live timer. It
does not stop a second copy of the app launching.

The mutex carries an explicit DACL. With default security, a copy of the app
started elevated (Run as administrator) creates a mutex only SYSTEM and
Administrators can open, so the unelevated installer gets access denied, treats
the app as not running, and replaces files under it. MUTEX_DACL_SDDL keeps full
access for SYSTEM, Administrators and the owner and lets Everyone do nothing
but wait on it (SYNCHRONIZE), which is all a mutex check needs.

installer/KluteTimer.iss repeats APP_MUTEX_NAME; tests/test_packaging.py keeps
the two in step.
"""
import ctypes
from ctypes import wintypes
from typing import Optional

from src.logger import get_logger

APP_MUTEX_NAME = "KluteTimer-AppMutex"

# GA = full access; 0x00100000 = SYNCHRONIZE. SY = SYSTEM, BA = Administrators,
# OW = the owner, WD = Everyone.
MUTEX_DACL_SDDL = "D:(A;;GA;;;SY)(A;;GA;;;BA)(A;;GA;;;OW)(A;;0x00100000;;;WD)"
_SDDL_REVISION_1 = 1

log = get_logger("single_instance")


class _SecurityAttributes(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", wintypes.LPVOID),
        ("bInheritHandle", wintypes.BOOL),
    ]


_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_create_mutex = _kernel32.CreateMutexW
_create_mutex.argtypes = [
    ctypes.POINTER(_SecurityAttributes),
    wintypes.BOOL,
    wintypes.LPCWSTR,
]
_create_mutex.restype = wintypes.HANDLE
_local_free = _kernel32.LocalFree
_local_free.argtypes = [wintypes.LPVOID]
_local_free.restype = wintypes.LPVOID

_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
_sddl_to_descriptor = _advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW
_sddl_to_descriptor.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.LPVOID),
    ctypes.POINTER(wintypes.ULONG),
]
_sddl_to_descriptor.restype = wintypes.BOOL

# Referenced for the life of the process. Windows closes the handles, and so
# releases the name, when the process exits.
_held_handles: list[int] = []


def _build_descriptor(name: str) -> Optional[int]:
    """Build the MUTEX_DACL_SDDL security descriptor. Returns None on failure.

    The caller frees a returned descriptor with LocalFree. Never raises: without
    it the mutex still works for an installer running at the app's own level.
    """
    descriptor = wintypes.LPVOID()
    try:
        ok = _sddl_to_descriptor(
            MUTEX_DACL_SDDL, _SDDL_REVISION_1, ctypes.byref(descriptor), None
        )
    except Exception as e:
        log.warning(
            f"could not build app mutex security, using default: {e}",
            extra={"context": "startup", "state": f"name={name}"},
        )
        return None

    if not ok or not descriptor.value:
        log.warning(
            "could not build app mutex security, using default: "
            f"WinError {ctypes.get_last_error()}",
            extra={"context": "startup", "state": f"name={name}"},
        )
        return None

    return descriptor.value


def hold_app_mutex(name: str = APP_MUTEX_NAME) -> Optional[int]:
    """Create the named mutex and keep it. Returns the handle, or None on failure.

    Never raises: failing here only means the installer cannot detect the
    running app, which must not stop the app itself from launching.
    """
    descriptor = _build_descriptor(name)
    try:
        if descriptor:
            attributes = _SecurityAttributes(
                ctypes.sizeof(_SecurityAttributes), descriptor, False
            )
            handle = _create_mutex(ctypes.byref(attributes), False, name)
        else:
            handle = _create_mutex(None, False, name)
        error = ctypes.get_last_error()
    except Exception as e:
        log.warning(
            f"could not create app mutex: {e}",
            extra={"context": "startup", "state": f"name={name}"},
        )
        return None
    finally:
        if descriptor:
            _local_free(descriptor)

    if not handle:
        log.warning(
            f"could not create app mutex: WinError {error}",
            extra={"context": "startup", "state": f"name={name}"},
        )
        return None

    _held_handles.append(handle)
    return handle
