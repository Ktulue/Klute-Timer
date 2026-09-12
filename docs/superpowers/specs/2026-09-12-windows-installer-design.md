# Windows Installer — Design Spec

**Date:** 2026-09-12
**Branch:** `feat/windows-installer`
**Status:** Implemented; updated after final code review, security review, and red-team review (see Revisions)

## Background

Klute Timer ships as a PyInstaller one-folder build (`dist\KluteTimer\KluteTimer.exe` plus `_internal\`) that the user copies and deletes by hand. It never appears in Windows Settings > Apps > Installed apps, which is where the user uninstalls software.

PR #6 (d9a5068) moved all user data to `%APPDATA%\KluteTimer` so a rebuild cannot destroy it. The side effect is that deleting the app folder now leaves settings and logs behind, and the README documents two folders to delete manually. The operating system should own that.

There is no version string anywhere in the project. An installer and an uninstall entry both need one.

## Goals

- A real installer, `KluteTimerSetup-<version>.exe`, that registers an Installed apps entry with the correct name, icon, version, and publisher, and a working uninstall.
- Uninstall that removes the program completely and asks, deliberately, whether to remove user data.
- One version string, defined once, read by the exe's version resource, the installer, the uninstall entry, and the running app.
- Install, upgrade, and uninstall never corrupt or kill a running timer.
- The same PR rebuilds the exe, so the installer ships the app it describes.

## Non-Goals

- **Code signing.** A certificate costs roughly $200-400/year plus identity vetting, and SmartScreen reputation still has to accumulate afterwards. The installer ships unsigned; the README documents the **More info > Run anyway** step. This is a conscious call, revisit if the app is distributed widely.
- **Per-machine install** or an install-scope choice. See Decision 1.
- **One-file PyInstaller build.** See Decision 4.
- **Single-instance enforcement.** The app mutex exists so the installer can detect a running app; it does not stop a second copy launching.
- **Auto-update, start-with-Windows, MSI/enterprise deployment.**
- **Non-Windows builds.** The app is Windows-only (`winsound` is imported unguarded).

## Decisions

### 1. Per-user install

Install into `%LOCALAPPDATA%\Programs\KluteTimer` with `PrivilegesRequired=lowest`; the uninstall entry lands under HKCU.

**Why:** user data is already per-user (`%APPDATA%`), so app and data share one scope. No UAC prompt on install, upgrade, or uninstall, and streaming PCs are effectively single-account. A per-machine install would share the app but not the data, making "delete my data" ambiguous. Offering both would double the exe-level verification matrix.

The install folder is fixed (`DisableDirPage=yes`). Because the folder is always ours and the app writes nothing into it, uninstall can delete it wholesale.

### 2. Uninstall asks about user data, default keep

On a non-silent uninstall, a Yes/No message box asks whether to also delete `%APPDATA%\KluteTimer`. **No is the default button.** Only Yes deletes it.

- The prompt runs at `usAppMutexCheck`, which comes before Inno's own uninstall `AppMutex` check: asking any later would leave the box open past that check, during which the user could start Klute Timer again underneath it. The answer is stored in a `DeleteDataOnUninstall` variable; the folder itself is deleted only at `usPostUninstall`, once the program itself has been removed without error.
- Wording names the folder explicitly, lists what it holds (settings, presets, logs, timer text files, and anything else saved there, such as custom sounds), and states that a custom output folder chosen elsewhere is not touched.
- If deleting the folder fails (for example because another program, such as OBS, still has a file in it open), an informational message box names the folder and tells the user to delete it by hand; the uninstall itself still succeeds.
- A silent uninstall (`/SILENT`, `/VERYSILENT`) keeps data without asking.
- An upgrade installs over the existing version and does not run the uninstaller, so it never prompts and never deletes data.
- A custom output folder outside `%APPDATA%\KluteTimer` is never deleted, under any answer. The user chose it and it may contain other overlay files. If the configured output folder is inside the data folder, it goes with the data folder on Yes.

**Why:** always-keep fails the goal of the feature; always-delete is hostile to the common "uninstall and reinstall to fix it" habit. Asking, defaulting to the non-destructive answer, means anything left on disk was explicitly chosen.

### 3. Inno Setup 6

**Why:** per-user install, the HKCU uninstall entry, the uninstall icon, and running-app detection (`AppMutex`) are all declarative. The Decision 2 prompt is a short `[Code]` block. The version arrives on the compiler command line through the preprocessor. NSIS would need hand-written uninstall registry keys and per-user plumbing; WiX/MSI cannot show custom dialogs when uninstalled from Windows Settings, which rules out Decision 2.

Build dependency: `winget install JRSoftware.InnoSetup`, which provides `ISCC.exe`.

### 4. Keep the one-folder PyInstaller layout

**Why:** the installer already provides the single distributable file, which was the only real benefit of one-file. One-file would add per-launch extraction delay, leave `%TEMP%\_MEI*` folders behind whenever the app is killed (a new orphaned-files problem), raise antivirus false-positive rates, and require re-verifying the pywebview, WebView2, and pystray behavior PR #4 settled. `KluteTimer.spec` layout and `resource_path()` are unchanged.

### 5. Version lives in `src/version.py`

`__version__ = "1.0.0"` is the single definition. Starting at 1.0.0 marks the first release a stranger can install and uninstall like real software.

**Why:** a Python import behaves identically in source and frozen builds, honoring the PR #6 rule that the exe must not take code paths the test suite never sees. A `VERSION` text file would force a new frozen-only runtime file read through `resource_path()`, the bug class PR #5 shipped. Git-tag versioning breaks builds from a zip and still needs a generated file.

### 6. Running app is detected, never killed

The app holds a named mutex, `KluteTimer-AppMutex`, for its whole lifetime. The installer declares `AppMutex=KluteTimer-AppMutex`, so setup and uninstall both stop and tell the user to close Klute Timer (including a copy minimized to the tray) before continuing. `CloseApplications=no` turns off Restart Manager auto-close so there is exactly one clear dialog and no path that force-kills a timer mid-stream.

The mutex carries an explicit DACL (`MUTEX_DACL_SDDL` in `src/single_instance.py`): full access for SYSTEM, Administrators, and the owner, and `SYNCHRONIZE` only for Everyone. Without it, a copy of the app started elevated (Run as administrator) creates the mutex under the default security descriptor, which only SYSTEM and Administrators can open; an unelevated installer then gets access denied, treats the app as not running, and replaces files under it. Granting Everyone `SYNCHRONIZE` -- enough to wait on the mutex, nothing more -- is what lets an unelevated installer detect an elevated app.

`PrepareToInstall` in `[Code]` re-checks `CheckForMutexes('KluteTimer-AppMutex')` a second time, immediately before Setup copies a single file. It runs while the app may still be open, which is what actually catches a running app before `[InstallDelete]` removes `{app}\_internal`: relying on the `AppMutex` directive alone would leave a window where unlocked parts of `_internal` are deleted out from under a live timer before the directive gets another chance to check.

## Architecture

```
src/version.py ──────────┬──> KluteTimer.spec  (EXE version resource)
  __version__            ├──> build.bat ──/DAppVersion──> installer/KluteTimer.iss
  version_tuple()        └──> src/app.py  (startup log, get_version() API -> Settings panel)

src/single_instance.py ──> src/app.py main()  holds KluteTimer-AppMutex
  APP_MUTEX_NAME  <── must equal ──  AppMutex= in installer/KluteTimer.iss

build.bat: rescue legacy config -> read version -> PyInstaller -> find ISCC -> compile installer
  dist\KluteTimer\KluteTimer.exe          (the app, as today)
  dist\installer\KluteTimerSetup-1.0.0.exe (new)
```

## Components

### `src/version.py` (new)

- `__version__: str = "1.0.0"` — dotted `MAJOR.MINOR.PATCH`.
- `version_tuple() -> tuple[int, int, int, int]` — `(major, minor, patch, 0)`, the four-part form a Windows `VSVersionInfo` requires.

### `src/single_instance.py` (new)

- `APP_MUTEX_NAME = "KluteTimer-AppMutex"`.
- `MUTEX_DACL_SDDL` — an explicit security descriptor, `D:(A;;GA;;;SY)(A;;GA;;;BA)(A;;GA;;;OW)(A;;0x00100000;;;WD)`: full access for SYSTEM, Administrators, and the owner; `SYNCHRONIZE` (`0x00100000`) only for Everyone. See Decision 6 for why.
- `_build_descriptor(name)` — converts `MUTEX_DACL_SDDL` via `advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW`. Returns `None` on any failure or exception (logged as a warning, never raised), which falls back to the default DACL.
- `hold_app_mutex()` — calls `kernel32.CreateMutexW` via `ctypes`, passing a `_SecurityAttributes` struct built from `_build_descriptor()`'s result when one was built, or `None` (default security) otherwise; frees the descriptor with `LocalFree` afterwards. Returns the handle. The module keeps a reference so it stays open for the process lifetime; Windows releases it when the process exits. Failure to create the mutex is logged and swallowed: it must never stop the app launching.
- Does not check `ERROR_ALREADY_EXISTS` or refuse a second instance (out of scope).

### `src/app.py` (modified)

- `main()` calls `hold_app_mutex()` before the window is created.
- New module-level `log_startup() -> None` logs one line, `Klute Timer <version> starting`, with `state` carrying `frozen=<bool> exe=<sys.executable> data_dir=<DATA_DIR>`. `main()` calls it immediately after `setup_logger()`. It is a separate function so it can be tested without `main()` opening a webview window.
- New `Api.get_version() -> str` returning `__version__`.

### Frontend (modified)

The Settings modal shows `Klute Timer v<version>` (fetched through `get_version()`), styled as secondary text at the bottom of the settings body. No other UI change.

### `KluteTimer.spec` (modified)

Imports `__version__` and `version_tuple` from `src.version` and passes a `PyInstaller.utils.win32.versioninfo.VSVersionInfo` to `EXE(version=...)` with `FileVersion`/`ProductVersion` set from the tuple and string, `ProductName` "Klute Timer", `CompanyName` "Ktulue", `FileDescription` "Klute Timer", `OriginalFilename` "KluteTimer.exe". PyInstaller 6.22 accepts a `VSVersionInfo` object directly (verified in `PyInstaller.building.api.EXE`). The spec needs `pathex=["."]` (already present) and the build to run from the repo root (build.bat already `cd`s there) for the import to resolve.

### `installer/KluteTimer.iss` (new)

- `#ifndef AppVersion` → `#error` so the script cannot compile without the version supplied by build.bat. No version literal appears in the file.
- `#if Ver < EncodeVer(6,7,0)` → `#error`, pointing at `winget upgrade JRSoftware.InnoSetup`. The script is built and verified with Inno Setup 6.7; refusing an older compiler outright avoids it silently building a subtly different installer.
- `[Setup]`:
  - `AppId={{32085ADC-A6C1-4CF4-A9CE-7DAD72791E68}` — fixed forever; upgrades match on it.
  - `AppName=Klute Timer`, `AppVersion={#AppVersion}`, `AppVerName=Klute Timer {#AppVersion}`, `AppPublisher=Ktulue`, `AppPublisherURL`/`AppSupportURL=https://github.com/Ktulue/Klute-Timer`.
  - `PrivilegesRequired=lowest`, `DefaultDirName={autopf}\KluteTimer` (resolves to `%LOCALAPPDATA%\Programs\KluteTimer` when not elevated), `DisableDirPage=yes`, `DefaultGroupName=Klute Timer`, `DisableProgramGroupPage=yes`.
  - `AppMutex=KluteTimer-AppMutex`, `CloseApplications=no`.
  - `SetupIconFile=..\assets\KluteTimer.ico`, `UninstallDisplayIcon={app}\KluteTimer.exe`, `UninstallDisplayName=Klute Timer`.
  - `OutputDir=..\dist\installer`, `OutputBaseFilename=KluteTimerSetup-{#AppVersion}`, `Compression=lzma2`, `SolidCompression=yes`, `WizardStyle=modern`, `ArchitecturesAllowed=x64compatible`, `ArchitecturesInstallIn64BitMode=x64compatible`.
- `[InstallDelete]`: `Type: filesandordirs; Name: "{app}\_internal"; Check: IsDefaultInstallDir` so an upgrade never mixes old and new bundled libraries, and never touches `_internal` if the user installed somewhere other than the default folder.
- `[Files]`: `..\dist\KluteTimer\*` → `{app}`, `recursesubdirs createallsubdirs ignoreversion`, `Excludes: "\config.json,\logs\*,\output\*"`. The leading backslashes anchor each pattern to the top of `dist\KluteTimer` so they only ever match the real config/logs/output there, never a same-named file nested under `_internal`. A pre-`%APPDATA%` build could otherwise leave user data in `dist\KluteTimer`, and this stops it from being packaged.
- `[Tasks]`: `desktopicon`, "Create a desktop shortcut", checked by default.
- `[Icons]`: `{autoprograms}\Klute Timer` always; `{autodesktop}\Klute Timer` when `desktopicon`. Both carry `WorkingDir: "{app}"` and are named `Klute Timer.lnk`, so the installer replaces the shortcut `create_shortcut.ps1` used to make.
- `[Run]`: launch `{app}\KluteTimer.exe`, `postinstall nowait skipifsilent`, "Launch Klute Timer", `Check: not IsAdmin` -- skipped when Setup itself runs elevated, since the launched app would otherwise inherit administrator rights it should never have.
- `[UninstallDelete]`: `Type: filesandordirs; Name: "{app}"; Check: IsDefaultInstallDir`.
- `[Code]`:
  - `function IsDefaultInstallDir: Boolean` compares `{app}` against `{autopf}\KluteTimer`; it gates both `[InstallDelete]` and `[UninstallDelete]` so a non-default install location is never wiped.
  - `function PrepareToInstall` calls `CheckForMutexes('KluteTimer-AppMutex')` before Setup copies a single file (see Decision 6).
  - `CurUninstallStepChanged(CurUninstallStep: TUninstallStep)`: at `usAppMutexCheck`, if not `UninstallSilent` and the data folder exists, show `MsgBox(..., mbConfirmation, MB_YESNO or MB_DEFBUTTON2)` and store the answer in `DeleteDataOnUninstall`; at `usPostUninstall`, if `DeleteDataOnUninstall`, `DelTree(ExpandConstant('{userappdata}\KluteTimer'), True, True, True)`, showing an informational `MsgBox` if it fails. If there is no data folder there is nothing to ask about, so no prompt. The message shows the expanded path (for example `C:\Users\<name>\AppData\Roaming\KluteTimer`) so the user sees exactly what would be deleted:

  > Also delete your Klute Timer data folder?
  >
  > C:\Users\<name>\AppData\Roaming\KluteTimer
  >
  > This removes your settings, presets, logs, timer text files, and anything else saved there, such as custom sounds. Choose No to keep it for a future reinstall. A custom output folder you chose somewhere else is never deleted.

### `build.bat` (modified)

1. Rescue a pre-`%APPDATA%` config (unchanged).
2. Read the version with a one-liner that validates `__version__` is a plain `MAJOR.MINOR.PATCH` string (`re.fullmatch(r'\d+\.\d+\.\d+', v, re.ASCII)` -- `re.ASCII` so a Unicode digit, such as an Arabic-indic numeral, cannot pass where `\d` alone would let it). It prints nothing and exits non-zero with a descriptive message otherwise, so a bad version never reaches a file name or ISCC. Then delete any existing installer for the same version before the build starts, confirming the delete actually worked (failing loudly if not), so a failed build can never leave an old installer looking like the new one.
3. Run PyInstaller (unchanged).
4. Locate `ISCC.exe`, in order: `PATH` (via `where "$PATH:ISCC.exe"`, which never matches the current folder), then `%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe`, then `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`. If none is found, fail with: `Inno Setup 6 was not found. Install it with:  winget install JRSoftware.InnoSetup`. Otherwise echo the resolved path before using it.
5. `"%ISCC%" /Q "/DAppVersion=%KT_VERSION%" installer\KluteTimer.iss` (the switch is quoted so a version is never split on its dots); fail on non-zero exit with a neutral hint pointing at Inno Setup older than 6.7 or the installer file being open, rather than a stale Inno version number.
6. Print both artifact paths and the settings path.

### `scripts/create_shortcut.ps1` (deleted)

The installer creates Start Menu and desktop shortcuts. The script pointed at `dist\KluteTimer`, which is now a build intermediate rather than a place to run the app from.

### Unchanged

`src/paths.py` (`get_data_dir()`, `resource_path()`, `get_legacy_dir()`, `migrate_legacy_config()`), the one-folder spec layout, `.gitignore` (`dist/` already covers `dist\installer\`). From the installed location, `get_legacy_dir()` resolves to the install folder, which never contains `config.json`, so migration is a harmless no-op. Anyone still running from `dist\KluteTimer` was migrated by build.bat or by their first PR #6 launch.

## README

- **Install** (new, leads Setup): download or build `KluteTimerSetup-<version>.exe`, run it; no admin rights needed; unsigned, so on the SmartScreen screen click **More info > Run anyway**; installs to `%LOCALAPPDATA%\Programs\KluteTimer` with Start Menu and optional desktop shortcuts.
- **Build the standalone app** becomes **Build the installer**: `pip install -r requirements-dev.txt`, `winget install JRSoftware.InnoSetup`, `build.bat`; output paths; version bumped in `src/version.py` only. Remove `create_shortcut.ps1` instructions.
- **Where your files live**: replace "The app folder itself, `dist\KluteTimer\`" with the install folder.
- **Removing Klute Timer**: uninstall from Settings > Apps > Installed apps; explain the prompt, the No default, silent-uninstall behavior, and that a custom output folder is never deleted.
- **Packaging** operational note: point at the installer section.
- The Ko-fi support section already exists; leave it.

## Testing

TDD: each test is written and seen failing before the code it covers.

**Unit tests**

- `tests/test_version.py`: `__version__` matches `^\d+\.\d+\.\d+$`; `version_tuple()` returns four ints equal to the dotted parts plus `0`.
- `tests/test_single_instance.py`: after `hold_app_mutex()`, `kernel32.OpenMutexW(SYNCHRONIZE, False, APP_MUTEX_NAME)` returns a non-null handle (close it after); a `CreateMutexW` failure (patched to return 0) does not raise; reading the mutex's DACL back (`GetSecurityInfo` + `ConvertSecurityDescriptorToStringSecurityDescriptorW`) shows Everyone's ACE grants exactly `SYNCHRONIZE` and SYSTEM/Administrators keep the mutex's full-access mask; a `_sddl_to_descriptor` failure or exception still creates the mutex, with the default DACL.
- `tests/test_app_version.py`: `Api.get_version()` returns `__version__` (using the existing `patch("src.app.StreamerbotClient")` convention); `log_startup()` writes a log line containing the version and `frozen=False`.

**Packaging-drift tests** (`tests/test_packaging.py`, static reads of committed files)

- `installer/KluteTimer.iss` contains `PrivilegesRequired=lowest`, `DisableDirPage=yes`, `CloseApplications=no`, an `AppId=` line, and `AppMutex=` equal to `APP_MUTEX_NAME`; a minimum-Inno-version guard (`#if Ver < EncodeVer(6,7,0)`); the `[Files]` `Excludes` anchored to the source tree's root; `[InstallDelete]` and `[UninstallDelete]` both gated on `Check: IsDefaultInstallDir`; both `[Icons]` entries carry `WorkingDir`; the `[Run]` launch entry is gated on `not IsAdmin`.
- The `.iss` contains no literal matching `__version__` and uses `{#AppVersion}`.
- The `.iss` `[Code]` section uses `MB_DEFBUTTON2`, checks `UninstallSilent`, prompts at `usAppMutexCheck`, and deletes only at `usPostUninstall`.
- `KluteTimer.spec` imports from `src.version`.
- `build.bat` passes `/DAppVersion`, validates the version with `re.ASCII`, deletes a stale installer before building, and resolves `ISCC.exe` from `PATH` before Program Files or LocalAppData.
- `scripts/create_shortcut.ps1` does not exist.

These guard against the two files drifting from the Python they depend on; they do not replace installing.

The full suite (`python -m pytest -q`, currently 220 passing) must stay green.

## Verification: the installed exe is the arbiter

A passing suite does not close this out. Verification is done against the built installer and the installed app.

**Safety first**

- Back up the real `%APPDATA%\KluteTimer` to the session scratchpad before any install or uninstall. The uninstaller operates on the real folder and `KLUTE_TIMER_DATA_DIR` does not reach it. Restore it when verification ends.
- Ask the user before `winget install JRSoftware.InnoSetup`.
- Ask the user before closing a running `KluteTimer.exe` (it holds the log open and blocks a rebuild with WinError 32).

**Checks**

1. `build.bat` produces `dist\KluteTimer\KluteTimer.exe` and `dist\installer\KluteTimerSetup-1.0.0.exe`. The exe's Properties > Details shows version 1.0.0, product Klute Timer, company Ktulue.
2. Run the installer: no UAC prompt. Settings > Apps > Installed apps lists **Klute Timer**, version 1.0.0, publisher Ktulue, with the app icon. The HKCU `...\Uninstall\{32085ADC-...}_is1` key exists.
3. Launch from the Start Menu shortcut. The four `.txt` files exist in `%APPDATA%\KluteTimer\output`; the Settings panel shows absolute paths and `Klute Timer v1.0.0`; the log has the startup line with `frozen=True` and the installed exe path.
4. With the app running (window closed to tray), run the installer again and start an uninstall: both show the "Klute Timer is running" dialog and change nothing.
5. Set a custom output folder. Uninstall, answer **No**. The install folder, shortcuts, and uninstall entry are gone; `%APPDATA%\KluteTimer` and the custom folder remain. Reinstall and launch: presets and the custom output folder are intact.
6. Uninstall, answer **Yes**. `%APPDATA%\KluteTimer` is gone; the custom output folder still exists; `%LOCALAPPDATA%\Programs\KluteTimer`, the Start Menu and desktop shortcuts, and the HKCU uninstall key are all gone.
7. Restore the backed-up data folder.

## Risks

- **`{autopf}` resolution:** with `PrivilegesRequired=lowest` and no override dialog, Inno maps `{autopf}` to `{userpf}` (`%LOCALAPPDATA%\Programs`). Verified by check 2, not assumed.
- **Mutex visibility:** the mutex is created in the session namespace (no `Global\` prefix). Inno's `AppMutex` check runs in the same user session, so this matches. Verified by check 4.
- **Existing desktop shortcut:** the installer's `Klute Timer.lnk` overwrites the old one pointing at `dist\`. If the user declines the desktop task, the old shortcut remains and points at the dev build; the README notes this.

## Revisions

2026-09-12: updated after final code review, security review, and red-team review.

- Gave the app mutex an explicit DACL (`MUTEX_DACL_SDDL`) so Everyone can still `SYNCHRONIZE` on it, letting an unelevated installer detect an app running elevated.
- Added `PrepareToInstall` to re-check the mutex immediately before Setup copies a file, closing the window where `[InstallDelete]` could remove `_internal` out from under a live timer.
- Moved the uninstall data prompt to `usAppMutexCheck` (before Inno's own uninstall `AppMutex` check) and the actual `DelTree` to `usPostUninstall` (after the program itself is removed without error), with an informational message if the delete fails.
- Reworded the data-prompt to name everything the folder can hold, including "anything else saved there, such as custom sounds".
- Anchored `[Files]` `Excludes` to the source tree's root (`\config.json,\logs\*,\output\*`) so they cannot also match a same-named file nested under `_internal`.
- Gated `[InstallDelete]` and `[UninstallDelete]` on `IsDefaultInstallDir`, and the post-install `[Run]` launch on `not IsAdmin`; added `WorkingDir` to both `[Icons]` entries.
- Added a minimum Inno Setup 6.7 guard (`#if Ver < EncodeVer(6,7,0)`) so the script refuses to compile on an older, unverified version.
- Hardened `build.bat`: `re.ASCII` on the version check so a Unicode digit cannot pass as `MAJOR.MINOR.PATCH`; delete (and confirm the delete of) a stale same-version installer before building; quote the `/DAppVersion` switch; look for `ISCC.exe` on `PATH` before Program Files or LocalAppData, echoing the resolved path; a neutral build-failure hint instead of a stale Inno version number.
- Corrected the README's upgrade guidance: a pre-`%APPDATA%` build has no migration code, so launching it does not carry settings over; the fix is to copy its `config.json` into `%APPDATA%\KluteTimer\` by hand before the first launch of the installed app.
