# Windows Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `KluteTimerSetup-1.0.0.exe`, a per-user Inno Setup installer that registers Klute Timer in Windows Settings > Apps > Installed apps with a working uninstall, plus a rebuilt exe that carries the same version.

**Architecture:** `src/version.py` is the single version definition, read by `KluteTimer.spec` (exe version resource), `build.bat` (passed to the Inno compiler), and the app (startup log, Settings panel). `src/single_instance.py` holds a named mutex so the installer's `AppMutex` can detect a running app. `installer/KluteTimer.iss` packages the unchanged one-folder PyInstaller output, and its `[Code]` asks at uninstall whether to delete `%APPDATA%\KluteTimer`, defaulting to No.

**Tech Stack:** Python 3.12, PyInstaller 6.22, Inno Setup 6 (`ISCC.exe`), pywebview, ctypes (kernel32), pytest, vanilla JS/HTML.

**Spec:** `docs/superpowers/specs/2026-09-12-windows-installer-design.md`

**Branch:** `feat/windows-installer` (already created from d9a5068, spec already committed)

## Global Constraints

- Windows-only. No non-Windows guards.
- Version: `1.0.0`, written only in `src/version.py`. No version literal in `installer/KluteTimer.iss`, `KluteTimer.spec`, or `build.bat`.
- Mutex name: `KluteTimer-AppMutex`, identical in `src/single_instance.py` and `installer/KluteTimer.iss`.
- Installer `AppId`: `{32085ADC-A6C1-4CF4-A9CE-7DAD72791E68}` (written `{{32085ADC-A6C1-4CF4-A9CE-7DAD72791E68}` in the `.iss`). Never change it.
- Display name `Klute Timer`; publisher `Ktulue`; URL `https://github.com/Ktulue/Klute-Timer`.
- Install folder: `%LOCALAPPDATA%\Programs\KluteTimer`, fixed, no UAC (`PrivilegesRequired=lowest`).
- Uninstall never deletes a custom output folder outside `%APPDATA%\KluteTimer`. It deletes `%APPDATA%\KluteTimer` only on an explicit Yes; No is the default button; silent uninstall keeps data.
- `src/paths.py` and the one-folder layout of `KluteTimer.spec` are not changed.
- TDD: write each test, run it, watch it fail, then implement.
- Test run: `python -m pytest -q` from the repo root. Baseline 162 passing.
- Commits: conventional prefix (`feat:`, `fix:`, `docs:`, `test:`), no emojis, no "Generated with Claude Code" footer, no claude.ai session URL. End each message with the trailer `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`, matching the repo's prior commits.
- Do not stage the untracked root `CLAUDE.md`.
- A running `KluteTimer.exe` blocks a rebuild (WinError 32). Ask the user before closing it. Ask before `winget install`.
- Open the PR and stop. Never merge.

---

## Files Touched

**Created:**
- `src/version.py` — the version string and its four-part tuple
- `src/single_instance.py` — the named app mutex
- `installer/KluteTimer.iss` — Inno Setup script
- `tests/test_version.py`
- `tests/test_single_instance.py`
- `tests/test_app_version.py`
- `tests/test_packaging.py` — static drift checks on spec, `.iss`, `build.bat`, README

**Modified:**
- `src/app.py` — `log_startup()`, `Api.get_version()`, `main()` calls both new pieces
- `frontend/index.html`, `frontend/js/app.js`, `frontend/css/style.css` — version line in Settings
- `KluteTimer.spec` — exe version resource
- `build.bat` — version read, Inno compile step
- `README.md` — install, build, file locations, removal

**Deleted:**
- `scripts/create_shortcut.ps1`

---

### Task 1: Version module

**Files:**
- Create: `src/version.py`
- Test: `tests/test_version.py`

**Interfaces:**
- Consumes: nothing
- Produces: `src.version.__version__: str` (`"1.0.0"`), `src.version.version_tuple() -> tuple[int, int, int, int]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_version.py`:

```python
import re

from src import version


def test_version_is_dotted_major_minor_patch():
    assert re.fullmatch(r"\d+\.\d+\.\d+", version.__version__)


def test_first_installable_release_is_1_0_0():
    assert version.__version__ == "1.0.0"


def test_version_tuple_is_the_dotted_parts_plus_zero(monkeypatch):
    monkeypatch.setattr(version, "__version__", "2.13.7")
    assert version.version_tuple() == (2, 13, 7, 0)


def test_version_tuple_matches_current_version():
    parts = tuple(int(p) for p in version.__version__.split("."))
    assert version.version_tuple() == parts + (0,)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_version.py -v`
Expected: collection error, `ImportError: cannot import name 'version' from 'src'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/version.py`:

```python
"""The one place Klute Timer's version is written.

KluteTimer.spec reads it for the exe's version resource, build.bat passes it to
the Inno Setup compiler for the installer and the Installed apps entry, and the
app shows it in Settings and the log. Bump it here and nowhere else.
"""

__version__ = "1.0.0"


def version_tuple() -> tuple[int, int, int, int]:
    """The four-part (major, minor, patch, 0) form Windows version resources use."""
    major, minor, patch = (int(part) for part in __version__.split("."))
    return (major, minor, patch, 0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_version.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/version.py tests/test_version.py
git commit -m "feat: add a single version definition in src/version.py" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: App mutex

**Files:**
- Create: `src/single_instance.py`
- Test: `tests/test_single_instance.py`

**Interfaces:**
- Consumes: `src.logger.get_logger`
- Produces: `src.single_instance.APP_MUTEX_NAME: str` (`"KluteTimer-AppMutex"`), `src.single_instance.hold_app_mutex(name: str = APP_MUTEX_NAME) -> Optional[int]` (handle, or `None` on failure; never raises). Module attribute `_create_mutex` is the patch point for tests.

- [ ] **Step 1: Write the failing test**

Create `tests/test_single_instance.py`. Each test uses a unique mutex name, so a real Klute Timer running on the machine cannot make a test pass by accident; the first test also asserts the name is absent before holding it.

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_single_instance.py -v`
Expected: collection error, `ImportError: cannot import name 'single_instance' from 'src'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/single_instance.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_single_instance.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/single_instance.py tests/test_single_instance.py
git commit -m "feat: hold a named mutex so the installer can detect a running app" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Wire version and mutex into the app and Settings panel

**Files:**
- Modify: `src/app.py` (imports near line 12-18; `Api.get_presets` near line 272; `main()` near line 420)
- Modify: `frontend/index.html` (settings body, after the Log Folder section near line 163)
- Modify: `frontend/js/app.js` (the `pywebviewready` handler near line 13)
- Modify: `frontend/css/style.css` (after `.settings-hint` near line 496)
- Test: `tests/test_app_version.py`

**Interfaces:**
- Consumes: `src.version.__version__`, `src.single_instance.hold_app_mutex()`
- Produces: `src.app.log_startup() -> None`, `src.app.Api.get_version() -> str`, DOM element `#settings-version`

- [ ] **Step 1: Write the failing test**

Create `tests/test_app_version.py`:

```python
import inspect
import os
from unittest.mock import patch

import src.app as app_module
from src.logger import setup_logger
from src.version import __version__

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts: str) -> str:
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def test_get_version_returns_the_app_version(tmp_path, monkeypatch):
    monkeypatch.setattr("src.app.DATA_DIR", str(tmp_path))
    with patch("src.app.StreamerbotClient"):
        api = app_module.Api()

    assert api.get_version() == __version__


def test_log_startup_records_version_build_kind_and_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("src.app.DATA_DIR", str(tmp_path))
    log_dir = tmp_path / "logs"
    setup_logger(log_dir=str(log_dir))

    app_module.log_startup()

    content = (log_dir / "klute-timer.log").read_text(encoding="utf-8")
    assert f"Klute Timer {__version__} starting" in content
    assert "frozen=False" in content
    assert f"data_dir={tmp_path}" in content


def test_main_logs_startup_and_holds_the_app_mutex():
    # main() opens a real webview window, so check its wiring statically.
    source = inspect.getsource(app_module.main)
    assert "log_startup()" in source
    assert "hold_app_mutex()" in source


def test_settings_panel_shows_the_version():
    assert 'id="settings-version"' in _read("frontend", "index.html")
    assert "pywebview.api.get_version()" in _read("frontend", "js", "app.js")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app_version.py -v`
Expected: 4 failed — `AttributeError: 'Api' object has no attribute 'get_version'`, `AttributeError: module 'src.app' has no attribute 'log_startup'`, an `AssertionError` on `"log_startup()" in source`, and an `AssertionError` on `id="settings-version"`.

- [ ] **Step 3: Implement the backend**

In `src/app.py`, add to the imports after `from src.logger import setup_logger, get_logger`:

```python
from src.single_instance import hold_app_mutex
from src.version import __version__
```

Add this method to `Api` directly above `def get_presets(self)`:

```python
    def get_version(self) -> str:
        return __version__
```

Add this module-level function directly above `def start_backend(`:

```python
def log_startup() -> None:
    """Record which build is running, so every log says what produced it."""
    log.info(
        f"Klute Timer {__version__} starting",
        extra={
            "context": "startup",
            "state": (
                f"frozen={getattr(sys, 'frozen', False)} "
                f"exe={sys.executable} data_dir={DATA_DIR}"
            ),
        },
    )
```

Change the start of `main()` from:

```python
def main() -> None:
    setup_logger(log_dir=os.path.join(DATA_DIR, "logs"))

    api = Api()
```

to:

```python
def main() -> None:
    setup_logger(log_dir=os.path.join(DATA_DIR, "logs"))
    log_startup()
    hold_app_mutex()

    api = Api()
```

- [ ] **Step 4: Implement the frontend**

In `frontend/index.html`, after the closing `</section>` of the Log Folder section and before the `</div>` that closes `settings-body`, add:

```html
                <p class="settings-version" id="settings-version"></p>
```

In `frontend/js/app.js`, change the `pywebviewready` handler to:

```javascript
window.addEventListener('pywebviewready', async () => {
    const state = await pywebview.api.get_state();
    presets = await pywebview.api.get_presets();
    timers = state.timers;

    renderTimerCards();
    updateWsStatus(state.ws_status);
    setupEventListeners();
    await refreshPaths();

    const version = await pywebview.api.get_version();
    document.getElementById('settings-version').textContent = `Klute Timer v${version}`;
});
```

In `frontend/css/style.css`, directly after the `.settings-hint { ... }` rule, add:

```css
/* Which build is running: lets the user match the app to Installed apps. */
.settings-version {
    margin-top: 24px;
    padding-top: 16px;
    border-top: 1px solid var(--border);
    font-size: 12px;
    color: var(--text-secondary);
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_app_version.py -v`
Expected: 4 passed.

Run: `python -m pytest -q`
Expected: all pass (162 baseline + 11 new = 173).

- [ ] **Step 6: Commit**

```bash
git add src/app.py frontend/index.html frontend/js/app.js frontend/css/style.css tests/test_app_version.py
git commit -m "feat: log the running version and show it in Settings" -m "The app now holds its installer-visible mutex from startup." -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Exe version resource

**Files:**
- Modify: `KluteTimer.spec`
- Test: `tests/test_packaging.py` (create)

**Interfaces:**
- Consumes: `src.version.__version__`, `src.version.version_tuple()`
- Produces: `tests/test_packaging.py` with `ROOT` and `_read(*parts)` helpers that Tasks 5-7 extend

- [ ] **Step 1: Write the failing test**

Create `tests/test_packaging.py`:

```python
"""Static checks that the build files stay in step with the Python they depend on.

They catch drift (a hardcoded version, a renamed mutex) cheaply. They do not
replace building and installing: the installed exe is the arbiter.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts: str) -> str:
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


class TestSpec:
    def test_reads_version_from_src_version(self):
        spec = _read("KluteTimer.spec")
        assert "from src.version import __version__, version_tuple" in spec

    def test_passes_version_resource_to_exe(self):
        spec = _read("KluteTimer.spec")
        assert re.search(r"version\s*=\s*version_info", spec)

    def test_has_no_version_literal(self):
        spec = _read("KluteTimer.spec")
        assert not re.search(r"['\"]\d+\.\d+\.\d+['\"]", spec)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_packaging.py -v`
Expected: `test_reads_version_from_src_version` and `test_passes_version_resource_to_exe` FAIL; `test_has_no_version_literal` passes (it guards the implementation).

- [ ] **Step 3: Implement**

In `KluteTimer.spec`, replace the line:

```python
from PyInstaller.utils.hooks import collect_all
```

with:

```python
import sys

from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

# SPECPATH is the folder holding this spec (the repo root); PyInstaller
# defines it. Putting it on sys.path lets the spec import the app's version.
sys.path.insert(0, SPECPATH)
from src.version import __version__, version_tuple

# Shown in the exe's Properties > Details tab.
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=version_tuple(), prodvers=version_tuple()),
    kids=[
        StringFileInfo([
            StringTable("040904B0", [
                StringStruct("CompanyName", "Ktulue"),
                StringStruct("FileDescription", "Klute Timer"),
                StringStruct("FileVersion", __version__),
                StringStruct("InternalName", "KluteTimer"),
                StringStruct("OriginalFilename", "KluteTimer.exe"),
                StringStruct("ProductName", "Klute Timer"),
                StringStruct("ProductVersion", __version__),
            ]),
        ]),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)
```

In the `EXE(...)` call, after `icon="assets/KluteTimer.ico",` add:

```python
    version=version_info,
```

In the module docstring, change `(or just run build.bat, which also rescues settings from a pre-%APPDATA% install).` to `(or just run build.bat, which also builds the installer and rescues settings from a pre-%APPDATA% install).`

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_packaging.py -v`
Expected: 3 passed.

Also confirm the version object builds outside PyInstaller's spec namespace:

Run: `python -c "from PyInstaller.utils.win32.versioninfo import FixedFileInfo, VSVersionInfo; from src.version import version_tuple; print(VSVersionInfo(ffi=FixedFileInfo(filevers=version_tuple(), prodvers=version_tuple()), kids=[]).ffi.fileVersionMS)"`
Expected: `65536` (1.0 packed as `major << 16 | minor`).

The real check that the resource lands in the exe is Task 8, step 3.

- [ ] **Step 5: Commit**

```bash
git add KluteTimer.spec tests/test_packaging.py
git commit -m "feat: stamp KluteTimer.exe with a version resource from src/version.py" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Inno Setup script

**Files:**
- Create: `installer/KluteTimer.iss`
- Modify: `tests/test_packaging.py` (append class)

**Interfaces:**
- Consumes: `src.single_instance.APP_MUTEX_NAME`, `/DAppVersion=<version>` from the compiler command line, `dist\KluteTimer\` from PyInstaller, `assets\KluteTimer.ico`
- Produces: `dist\installer\KluteTimerSetup-<version>.exe` when compiled

- [ ] **Step 1: Write the failing test**

Append to `tests/test_packaging.py` (add `from src.single_instance import APP_MUTEX_NAME` and `from src.version import __version__` to its imports):

```python
class TestInstallerScript:
    ISS = ("installer", "KluteTimer.iss")

    def _directive(self, name: str) -> str:
        match = re.search(rf"^\s*{name}=(.*)$", _read(*self.ISS), re.MULTILINE)
        assert match, f"{name}= missing from KluteTimer.iss"
        return match.group(1).strip()

    def test_installs_per_user_without_uac(self):
        assert self._directive("PrivilegesRequired") == "lowest"
        assert self._directive("DefaultDirName") == r"{autopf}\KluteTimer"
        assert self._directive("DisableDirPage") == "yes"

    def test_app_id_is_fixed(self):
        assert self._directive("AppId") == "{{32085ADC-A6C1-4CF4-A9CE-7DAD72791E68}"

    def test_detects_running_app_by_the_same_mutex_name(self):
        assert self._directive("AppMutex") == APP_MUTEX_NAME
        assert self._directive("CloseApplications") == "no"

    def test_identity_matches_the_spec(self):
        assert self._directive("AppName") == "Klute Timer"
        assert self._directive("AppPublisher") == "Ktulue"
        assert self._directive("UninstallDisplayName") == "Klute Timer"

    def test_version_comes_only_from_the_command_line(self):
        iss = _read(*self.ISS)
        assert self._directive("AppVersion") == "{#AppVersion}"
        assert "#ifndef AppVersion" in iss
        assert __version__ not in iss
        assert not re.search(r"\d+\.\d+\.\d+", iss)

    def test_upgrade_clears_old_bundled_libraries(self):
        assert re.search(
            r'^\[InstallDelete\]\s*^Type: filesandordirs; Name: "\{app\}\\_internal"',
            _read(*self.ISS),
            re.MULTILINE,
        )

    def test_uninstall_removes_the_whole_install_folder(self):
        assert re.search(
            r'^\[UninstallDelete\]\s*^Type: filesandordirs; Name: "\{app\}"',
            _read(*self.ISS),
            re.MULTILINE,
        )

    def test_data_prompt_defaults_to_keep_and_skips_silent_uninstall(self):
        code = _read(*self.ISS).split("[Code]", 1)[1]
        assert "UninstallSilent" in code
        assert "MB_DEFBUTTON2" in code
        assert r"{userappdata}\KluteTimer" in code
        assert "DelTree" in code
        assert "IDYES" in code
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_packaging.py::TestInstallerScript -v`
Expected: 8 failed with `FileNotFoundError` for `installer\KluteTimer.iss`.

- [ ] **Step 3: Implement**

Create `installer/KluteTimer.iss`:

```ini
; Inno Setup script for Klute Timer.
;
; Build with build.bat, which reads the version from src\version.py and passes
; it here as /DAppVersion. Paths below are relative to this file's folder.
;
; Per-user install: no UAC prompt, files in %LOCALAPPDATA%\Programs\KluteTimer,
; uninstall entry under HKCU. User data lives in %APPDATA%\KluteTimer and is
; deleted on uninstall only if the user answers Yes to the prompt in [Code].

#ifndef AppVersion
  #error AppVersion is not defined. Build with build.bat, which passes /DAppVersion from src\version.py.
#endif

[Setup]
; AppId ties upgrades and the uninstall entry together. Never change it.
AppId={{32085ADC-A6C1-4CF4-A9CE-7DAD72791E68}
AppName=Klute Timer
AppVersion={#AppVersion}
AppVerName=Klute Timer {#AppVersion}
AppPublisher=Ktulue
AppPublisherURL=https://github.com/Ktulue/Klute-Timer
AppSupportURL=https://github.com/Ktulue/Klute-Timer
VersionInfoVersion={#AppVersion}
VersionInfoCompany=Ktulue
VersionInfoProductName=Klute Timer
PrivilegesRequired=lowest
DefaultDirName={autopf}\KluteTimer
DisableDirPage=yes
DefaultGroupName=Klute Timer
DisableProgramGroupPage=yes
; The app holds this mutex while running (src\single_instance.py). Setup and
; uninstall wait for the user to close it instead of killing a live timer.
AppMutex=KluteTimer-AppMutex
CloseApplications=no
SetupIconFile=..\assets\KluteTimer.ico
UninstallDisplayIcon={app}\KluteTimer.exe
UninstallDisplayName=Klute Timer
OutputDir=..\dist\installer
OutputBaseFilename=KluteTimerSetup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\KluteTimer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Icons]
Name: "{autoprograms}\Klute Timer"; Filename: "{app}\KluteTimer.exe"
Name: "{autodesktop}\Klute Timer"; Filename: "{app}\KluteTimer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\KluteTimer.exe"; Description: "Launch Klute Timer"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if (CurUninstallStep = usUninstall) and (not UninstallSilent) then
  begin
    DataDir := ExpandConstant('{userappdata}\KluteTimer');
    if DirExists(DataDir) then
    begin
      if MsgBox('Also delete your Klute Timer settings, presets, logs, and timer text files?' + #13#10 + #13#10 +
                DataDir + #13#10 + #13#10 +
                'Choose No to keep them for a future reinstall. A custom output folder you chose somewhere else is never deleted.',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
    end;
  end;
end;
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_packaging.py -v`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add installer/KluteTimer.iss tests/test_packaging.py
git commit -m "feat: add a per-user Inno Setup installer script" -m "Uninstall asks whether to delete %APPDATA%\KluteTimer, defaulting to No, and never touches a custom output folder elsewhere." -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: build.bat compiles the installer; retire create_shortcut.ps1

**Files:**
- Modify: `build.bat` (full rewrite below)
- Delete: `scripts/create_shortcut.ps1`
- Modify: `tests/test_packaging.py` (append class)

**Interfaces:**
- Consumes: `src.version.__version__`, `KluteTimer.spec`, `installer/KluteTimer.iss`
- Produces: `dist\KluteTimer\KluteTimer.exe`, `dist\installer\KluteTimerSetup-<version>.exe`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_packaging.py`:

```python
class TestBuildScript:
    def test_reads_version_from_src_version(self):
        assert "from src.version import __version__" in _read("build.bat")

    def test_passes_version_to_inno(self):
        bat = _read("build.bat")
        assert "/DAppVersion=%KT_VERSION%" in bat
        assert r"installer\KluteTimer.iss" in bat

    def test_explains_how_to_get_inno_when_missing(self):
        assert "winget install JRSoftware.InnoSetup" in _read("build.bat")

    def test_has_no_version_literal(self):
        assert not re.search(r"\d+\.\d+\.\d+", _read("build.bat"))

    def test_shortcut_script_is_retired(self):
        assert not os.path.exists(os.path.join(ROOT, "scripts", "create_shortcut.ps1"))
        assert "create_shortcut" not in _read("build.bat")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_packaging.py::TestBuildScript -v`
Expected: 4 failed (`test_has_no_version_literal` passes).

- [ ] **Step 3: Implement**

Delete the shortcut script:

```bash
git rm scripts/create_shortcut.ps1
```

Replace the whole of `build.bat` with (CRLF line endings, as the existing file has):

```bat
@echo off
REM Build Klute Timer: the app (dist\KluteTimer\KluteTimer.exe) and its
REM installer (dist\installer\KluteTimerSetup-<version>.exe).
cd /d "%~dp0"

set "KT_DATA=%APPDATA%\KluteTimer"

echo [1/4] Preserving settings from any older install...
REM Before user data moved to %APPDATA%, config.json lived beside the exe --
REM and PyInstaller deletes dist\KluteTimer before the new exe can migrate it.
REM Rescue it here, once. An existing %APPDATA% config is never overwritten.
if exist "dist\KluteTimer\config.json" (
    if not exist "%KT_DATA%\config.json" (
        if not exist "%KT_DATA%" mkdir "%KT_DATA%"
        copy /y "dist\KluteTimer\config.json" "%KT_DATA%\config.json" >nul
        echo     Carried your old settings over to %KT_DATA%
    )
)

echo [2/4] Reading the version from src\version.py...
set "KT_VERSION="
for /f "delims=" %%v in ('python -c "from src.version import __version__; print(__version__)"') do set "KT_VERSION=%%v"
if not defined KT_VERSION (
    echo.
    echo Build FAILED. Could not read the version from src\version.py.
    pause
    exit /b 1
)
echo     Version %KT_VERSION%

echo [3/4] Building KluteTimer.exe with PyInstaller...
python -m PyInstaller KluteTimer.spec --noconfirm
if errorlevel 1 (
    echo.
    echo Build FAILED. Is PyInstaller installed?  pip install -r requirements-dev.txt
    echo If KluteTimer.exe is running from dist\KluteTimer, close it and try again.
    pause
    exit /b 1
)

echo [4/4] Building the installer with Inno Setup...
set "ISCC="
for /f "delims=" %%i in ('where ISCC 2^>nul') do if not defined ISCC set "ISCC=%%i"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo.
    echo Build FAILED. Inno Setup 6 was not found. Install it with:
    echo     winget install JRSoftware.InnoSetup
    pause
    exit /b 1
)
"%ISCC%" /Q /DAppVersion=%KT_VERSION% installer\KluteTimer.iss
if errorlevel 1 (
    echo.
    echo Installer build FAILED. See the Inno Setup output above.
    pause
    exit /b 1
)

echo.
echo Done.
echo.
echo App:       dist\KluteTimer\KluteTimer.exe
echo Installer: dist\installer\KluteTimerSetup-%KT_VERSION%.exe
echo Settings:  %KT_DATA%
echo.
echo Run the installer to install or upgrade Klute Timer. Nothing you own lives
echo in dist\, so rebuilding is always safe.
pause
```

After writing, confirm CRLF endings: `file build.bat` should report `with CRLF line terminators`. If not, convert with `unix2dos build.bat` (or `python -c "p='build.bat'; d=open(p,newline='').read().replace('\r\n','\n').replace('\n','\r\n'); open(p,'w',newline='').write(d)"`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_packaging.py -v`
Expected: 16 passed.

Run: `python -m pytest -q`
Expected: all pass (162 baseline + 4 + 3 + 4 + 16 = 189).

- [ ] **Step 5: Commit**

```bash
git add build.bat tests/test_packaging.py
git commit -m "feat: build the installer from build.bat and retire create_shortcut.ps1" -m "The installer now creates the Start Menu and desktop shortcuts." -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: README

**Files:**
- Modify: `README.md`
- Modify: `tests/test_packaging.py` (append class)

**Interfaces:**
- Consumes: artifact names from Task 6, prompt behavior from Task 5
- Produces: nothing code-facing

- [ ] **Step 1: Write the failing test**

Append to `tests/test_packaging.py`:

```python
class TestReadme:
    def test_no_longer_mentions_the_shortcut_script(self):
        assert "create_shortcut" not in _read("README.md")

    def test_documents_installed_apps_uninstall_and_smartscreen(self):
        readme = _read("README.md")
        assert "Installed apps" in readme
        assert "Run anyway" in readme
        assert "winget install JRSoftware.InnoSetup" in readme

    def test_keeps_the_support_section(self):
        assert "ko-fi.com/ktulue" in _read("README.md")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_packaging.py::TestReadme -v`
Expected: `test_no_longer_mentions_the_shortcut_script` and `test_documents_installed_apps_uninstall_and_smartscreen` FAIL; the support-section test passes.

- [ ] **Step 3: Implement**

Make these edits to `README.md`.

**3a.** Replace everything from `## Setup` down to (not including) `### Streamer.bot Configuration` with:

````markdown
## Install

1. Get `KluteTimerSetup-<version>.exe`, either from a release or by building it
   yourself (see [Build the installer](#build-the-installer)).
2. Run it. No administrator rights are needed: Klute Timer installs for your
   Windows account only, into `%LOCALAPPDATA%\Programs\KluteTimer\`.
3. The installer is not code-signed, so Windows SmartScreen may say it
   "protected your PC" the first time. Click **More info**, then **Run anyway**.

The installer adds Klute Timer to the Start Menu and, unless you untick the
box, to your desktop. To upgrade, run a newer installer over the top: your
settings are kept. If Klute Timer is running, including minimized to the tray,
the installer asks you to close it first rather than stopping a live timer.

## Setup

### Requirements

- Windows 10 or 11
- Streamer.bot with WebSocket server enabled (default port: 8059)

### Run from source

For development, with Python 3.10+:

```bash
pip install -r requirements.txt
python -m src.app
```

### Build the installer

```bash
pip install -r requirements-dev.txt     # installs pyinstaller
winget install JRSoftware.InnoSetup     # one-time: the installer compiler
build.bat
```

`build.bat` produces two things:

| Output | What it is |
| --- | --- |
| `dist\KluteTimer\KluteTimer.exe` | The app, as a one-folder PyInstaller build with `_internal\` beside it |
| `dist\installer\KluteTimerSetup-<version>.exe` | The installer that packages it |

Notes:

- The version lives in one place, `src/version.py`. The exe, the installer, the
  Installed apps entry, and the Settings panel all read it from there.
- **Nothing you own lives in `dist\`.** Your settings, logs, and the default
  output folder live in `%APPDATA%\KluteTimer\`, so rebuilding is always safe.
- Close Klute Timer before rebuilding if it is running from `dist\KluteTimer\`;
  a running exe holds its log file open and blocks the build.
- If you used a desktop shortcut from an older build and untick the desktop
  shortcut box while installing, that old shortcut still points at
  `dist\KluteTimer\`. Delete it.
- The app icon is generated from `scripts\make_icon.py` (committed as
  `assets\KluteTimer.ico`); rerun it only if you change the icon design.

````

**3b.** In `## Where your files live`, replace the paragraph:

```markdown
The app folder itself, `dist\KluteTimer\`, holds only the program. You can
delete and rebuild it without losing anything.
```

with:

```markdown
The install folder, `%LOCALAPPDATA%\Programs\KluteTimer\`, holds only the
program. Installing, upgrading, or reinstalling never touches your data.
```

**3c.** Replace the whole `### Removing Klute Timer` section (heading and both paragraphs/list) with:

```markdown
### Removing Klute Timer

Uninstall it from **Windows Settings > Apps > Installed apps**: find
**Klute Timer**, open the **...** menu, and choose **Uninstall**. Close the app
first if it is running, including from the tray.

The uninstaller removes the program, its Start Menu and desktop shortcuts, and
its Installed apps entry. It then asks whether to also delete your settings,
presets, logs, and timer text files in `%APPDATA%\KluteTimer\`:

- **No** (the default) keeps them, so a future reinstall picks up exactly where
  you left off.
- **Yes** deletes that folder.

A custom output folder you chose somewhere else, such as
`C:\Streaming\Overlays\`, is never deleted either way. A silent uninstall
(`/SILENT` or `/VERYSILENT`) keeps your data without asking.
```

**3d.** In `### Packaging` under Operational Notes, replace the paragraph with:

```markdown
For day-to-day development the app launches via `python -m src.app` or
`launch.bat`. To install it like any other Windows app, build and run the
installer — see [Build the installer](#build-the-installer) under Setup.
```

Leave the `## Support` section at the end untouched.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_packaging.py -v`
Expected: 19 passed.

Run: `python -m pytest -q`
Expected: 192 passed.

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_packaging.py
git commit -m "docs: document installing, building, and uninstalling Klute Timer" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: Build, install, and verify the installed exe

No code in this task unless verification finds a bug. If it does, stop, use superpowers:systematic-debugging, fix with a failing test first, commit, rebuild, and restart this task from step 3.

The uninstall prompt and the Installed apps page need a human at the keyboard. Steps marked **(user)** are done by the user; ask them and wait.

Throughout, `$SCRATCH` is the session scratchpad directory. Commands are PowerShell.

- [ ] **Step 1: Back up real user data**

```powershell
$SCRATCH = '<session scratchpad path>'
Copy-Item "$env:APPDATA\KluteTimer" "$SCRATCH\KluteTimer-backup" -Recurse -Force
Get-ChildItem "$SCRATCH\KluteTimer-backup" -Recurse | Measure-Object | Select-Object Count
```

Expected: a non-zero count, and `config.json` present in the backup.

- [ ] **Step 2: Get prerequisites (ask first)**

Ask the user before each:
- Install Inno Setup: `winget install JRSoftware.InnoSetup`. Then locate `ISCC.exe` in `%LOCALAPPDATA%\Programs\Inno Setup 6\` or `%ProgramFiles(x86)%\Inno Setup 6\`.
- Close the running `KluteTimer.exe` (check with `Get-Process KluteTimer -ErrorAction SilentlyContinue | Select-Object Id, Path`).

- [ ] **Step 3: Build**

Run from the repo root: `cmd /c "build.bat < nul"` (the `< nul` answers the trailing `pause`).
Expected: `[1/4]` through `[4/4]`, then `Done.`; both `dist\KluteTimer\KluteTimer.exe` and `dist\installer\KluteTimerSetup-1.0.0.exe` exist.

Check the exe version resource:

```powershell
(Get-Item dist\KluteTimer\KluteTimer.exe).VersionInfo | Format-List ProductName, CompanyName, FileVersion, ProductVersion
```

Expected: `Klute Timer`, `Ktulue`, `1.0.0`, `1.0.0`.

- [ ] **Step 4: Install (user)**

Ask the user to run `dist\installer\KluteTimerSetup-1.0.0.exe` interactively, keep the desktop shortcut box ticked, and leave "Launch Klute Timer" ticked. Confirm with them that no UAC prompt appeared.

Then check:

```powershell
$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{32085ADC-A6C1-4CF4-A9CE-7DAD72791E68}_is1'
Get-ItemProperty $key | Format-List DisplayName, DisplayVersion, Publisher, DisplayIcon, InstallLocation, UninstallString
Test-Path "$env:LOCALAPPDATA\Programs\KluteTimer\KluteTimer.exe"
Test-Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Klute Timer.lnk"
Test-Path ([Environment]::GetFolderPath('Desktop') + '\Klute Timer.lnk')
```

Expected: `Klute Timer`, `1.0.0`, `Ktulue`, `DisplayIcon` pointing at `...\Programs\KluteTimer\KluteTimer.exe`, `InstallLocation` under `%LOCALAPPDATA%\Programs\KluteTimer\`; all three `Test-Path` are `True`.

Ask the user to open **Settings > Apps > Installed apps**, search "Klute", and confirm name, icon, version 1.0.0, and publisher Ktulue.

- [ ] **Step 5: Launched app behaves as a frozen install**

```powershell
Get-Process KluteTimer | Select-Object Id, Path
Get-ChildItem "$env:APPDATA\KluteTimer\output" -Filter *.txt | Select-Object Name
Select-String -Path "$env:APPDATA\KluteTimer\logs\klute-timer.log" -Pattern 'Klute Timer 1.0.0 starting' | Select-Object -Last 1
```

Expected: path under `%LOCALAPPDATA%\Programs\KluteTimer\`. The four `.txt` files exist only if the config's output folder is the default; if the restored real config uses a custom folder, check that folder instead. The log line contains `frozen=True` and `exe=` the installed path.

Ask the user to open Settings in the app and confirm: absolute paths for the output folder, every file, and the log folder; and `Klute Timer v1.0.0` at the bottom.

- [ ] **Step 6: Running-app detection (user)**

With the app still running (ask the user to close its window so it sits in the tray), ask the user to:
1. Run `KluteTimerSetup-1.0.0.exe` again. Expected: a dialog saying Klute Timer is running and must be closed; cancel it.
2. Start **Uninstall** from Installed apps. Expected: the same kind of dialog; cancel it.

Then confirm nothing changed: `Test-Path "$env:LOCALAPPDATA\Programs\KluteTimer\KluteTimer.exe"` is `True` and the process is still running.

- [ ] **Step 7: Uninstall answering No keeps data (user)**

Ask the user to quit Klute Timer from the tray menu. Set a custom output folder with the app closed:

```powershell
$custom = "$SCRATCH\custom-output"
New-Item -ItemType Directory -Force $custom | Out-Null
$cfgPath = "$env:APPDATA\KluteTimer\config.json"
$cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
$cfg | Add-Member -NotePropertyName output_dir -NotePropertyValue $custom -Force
$cfg | ConvertTo-Json -Depth 10 | Set-Content $cfgPath -Encoding utf8
```

Ask the user to launch Klute Timer from the Start Menu once (so the four files appear in `$custom`), quit it from the tray, then uninstall from Installed apps and answer **No** to the data prompt. Then:

```powershell
Test-Path "$env:LOCALAPPDATA\Programs\KluteTimer"
Test-Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Klute Timer.lnk"
Test-Path ([Environment]::GetFolderPath('Desktop') + '\Klute Timer.lnk')
Test-Path $key
Test-Path "$env:APPDATA\KluteTimer\config.json"
Get-ChildItem $custom -Filter *.txt | Select-Object Name
```

Expected: `False`, `False`, `False`, `False`, `True`, and four `.txt` files.

Ask the user to reinstall and launch. Then confirm `(Get-Content $cfgPath -Raw | ConvertFrom-Json).output_dir` still equals `$custom` and ask the user to confirm Settings shows the custom folder and their presets.

- [ ] **Step 8: Uninstall answering Yes removes data only (user)**

Ask the user to quit the app from the tray, uninstall from Installed apps, and answer **Yes**. Then:

```powershell
Test-Path "$env:APPDATA\KluteTimer"
Test-Path $custom
Get-ChildItem $custom -Filter *.txt | Select-Object Name
Test-Path "$env:LOCALAPPDATA\Programs\KluteTimer"
Test-Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Klute Timer.lnk"
Test-Path ([Environment]::GetFolderPath('Desktop') + '\Klute Timer.lnk')
Test-Path $key
```

Expected: `False`, `True`, four `.txt` files, then `False` for the rest.

- [ ] **Step 9: Restore real user data and leave the user installed**

```powershell
Copy-Item "$SCRATCH\KluteTimer-backup" "$env:APPDATA\KluteTimer" -Recurse -Force
Get-Content "$env:APPDATA\KluteTimer\config.json" -Raw | ConvertFrom-Json | Select-Object output_dir
```

Expected: the user's original `output_dir`. Ask the user whether they want Klute Timer reinstalled now (it is currently uninstalled). If yes, have them run the installer and confirm their presets appear.

Record the result of every step (pass, or what failed and how it was fixed) for the PR description.

---

### Task 9: Open the PR

- [ ] **Step 1: Final suite and clean tree**

Run: `python -m pytest -q`
Expected: 192 passed (or more, if Task 8 added regression tests).

Run: `git status --short`
Expected: only `?? CLAUDE.md`.

- [ ] **Step 2: Push and open the PR**

```bash
git push -u origin feat/windows-installer
gh pr create --base main --head feat/windows-installer --title "feat: Windows installer with an Installed apps uninstall entry" --body-file <scratchpad>/pr-body.md
```

Write `pr-body.md` first. Contents: why (no Installed apps entry, orphaned `%APPDATA%` data since PR #6); the six decisions with one-line reasons each (per-user, prompt defaulting to keep, Inno Setup, one-folder kept, `src/version.py`, unsigned on purpose); what changed by file; the Task 8 verification results step by step. No emojis, no "Generated with Claude Code" footer, no claude.ai session URL.

- [ ] **Step 3: Stop**

Tell the user: "PR #N is open — ready to merge when you give the word." Do not merge.
