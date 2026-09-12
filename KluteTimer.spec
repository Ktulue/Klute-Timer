# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build recipe for Klute Timer.

Build with:  pyinstaller KluteTimer.spec --noconfirm
(or just run build.bat, which also builds the installer and rescues settings from a pre-%APPDATA% install).

One-folder build -> dist/KluteTimer/KluteTimer.exe (+ _internal/). Everything in
that folder is disposable: the frontend UI is bundled read-only inside the app,
and config.json, logs/ and the default output/ live in %APPDATA%/KluteTimer so a
rebuild cannot delete the folder OBS is reading from.
"""
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

# pywebview (webview) and pystray pull in platform backends and data files that
# are easy to miss; collect_all grabs submodules, data and dylibs for each.
datas = [("frontend", "frontend")]
binaries = []
hiddenimports = []
for pkg in ("webview", "pystray"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    ["run.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KluteTimer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI app: no console window / no flash
    disable_windowed_traceback=False,
    icon="assets/KluteTimer.ico",
    version=version_info,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="KluteTimer",
)
