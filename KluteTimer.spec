# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build recipe for Klute Timer.

Build with:  pyinstaller KluteTimer.spec --noconfirm
(or just run build.bat, which also stages config.json/output next to the exe).

One-folder build -> dist/KluteTimer/KluteTimer.exe (+ _internal/). The frontend
UI is bundled read-only inside the app; config.json, output/, logs/ and sounds/
are resolved next to the exe at runtime so the user can edit presets and OBS can
read the output files.
"""
from PyInstaller.utils.hooks import collect_all

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
