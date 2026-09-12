import ctypes
import re
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


SE_KERNEL_OBJECT = 6
DACL_SECURITY_INFORMATION = 0x00000004
SDDL_REVISION_1 = 1
GENERIC_ALL = 0x10000000

# What ConvertSecurityDescriptorToStringSecurityDescriptorW actually returns
# for a mutex handle created with GA (full access) in the SDDL we hand in:
# MUTANT_ALL_ACCESS (STANDARD_RIGHTS_ALL | MUTANT_QUERY_STATE), not the
# literal string "GA". Confirmed by round-tripping MUTEX_DACL_SDDL through
# hold_app_mutex() and reading the DACL back.
MUTEX_FULL_ACCESS = 0x1F0001

_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
_get_security_info = _advapi32.GetSecurityInfo
_get_security_info.argtypes = [
    wintypes.HANDLE,
    ctypes.c_int,
    wintypes.DWORD,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_void_p),
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_void_p),
]
_get_security_info.restype = wintypes.DWORD
_sd_to_sddl = _advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW
_sd_to_sddl.argtypes = [
    ctypes.c_void_p,
    wintypes.DWORD,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.LPWSTR),
    ctypes.c_void_p,
]
_sd_to_sddl.restype = wintypes.BOOL
_local_free = _kernel32.LocalFree
_local_free.argtypes = [ctypes.c_void_p]
_local_free.restype = ctypes.c_void_p


def _dacl_sddl(handle: int) -> str:
    dacl = ctypes.c_void_p()
    descriptor = ctypes.c_void_p()
    error = _get_security_info(
        handle, SE_KERNEL_OBJECT, DACL_SECURITY_INFORMATION,
        None, None, ctypes.byref(dacl), None, ctypes.byref(descriptor),
    )
    assert error == 0, f"GetSecurityInfo failed: WinError {error}"
    try:
        text = wintypes.LPWSTR()
        assert _sd_to_sddl(
            descriptor, SDDL_REVISION_1, DACL_SECURITY_INFORMATION, ctypes.byref(text), None
        ), f"SDDL conversion failed: WinError {ctypes.get_last_error()}"
        try:
            return text.value
        finally:
            _local_free(ctypes.cast(text, ctypes.c_void_p))
    finally:
        _local_free(descriptor)


def _rights_granted_to(sddl: str, trustee: str) -> list[int]:
    rights = []
    for ace_type, _flags, mask, _guid, _inherit_guid, sid in re.findall(
        r"\(([^;]*);([^;]*);([^;]*);([^;]*);([^;]*);([^)]*)\)", sddl
    ):
        if ace_type != "A" or sid != trustee:
            continue
        if mask.lower().startswith("0x"):
            rights.append(int(mask, 16))
        elif mask == "GA":
            rights.append(GENERIC_ALL | SYNCHRONIZE)
    return rights


def test_everyone_can_wait_on_the_mutex_so_an_unelevated_installer_sees_an_elevated_app():
    handle = single_instance.hold_app_mutex(_unique_name())
    assert handle

    sddl = _dacl_sddl(handle)

    everyone_rights = _rights_granted_to(sddl, "WD")
    assert everyone_rights, sddl
    # Everyone gets exactly SYNCHRONIZE -- enough to detect the mutex, nothing broader.
    assert everyone_rights == [SYNCHRONIZE], sddl

    # SYSTEM and Administrators keep full access to the mutex.
    for trustee in ("SY", "BA"):
        rights = _rights_granted_to(sddl, trustee)
        assert rights == [MUTEX_FULL_ACCESS], (trustee, sddl)


def test_descriptor_build_failure_still_creates_the_mutex(monkeypatch):
    monkeypatch.setattr(single_instance, "_sddl_to_descriptor", lambda *args: 0)
    name = _unique_name()

    handle = single_instance.hold_app_mutex(name)

    assert handle
    assert _mutex_exists(name)


def test_descriptor_build_exception_still_creates_the_mutex(monkeypatch):
    def boom(*args):
        raise OSError("advapi32 unavailable")

    monkeypatch.setattr(single_instance, "_sddl_to_descriptor", boom)
    name = _unique_name()

    handle = single_instance.hold_app_mutex(name)

    assert handle
    assert _mutex_exists(name)
