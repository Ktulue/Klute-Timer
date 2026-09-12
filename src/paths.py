"""Where Klute Timer keeps the files the user owns.

Everything the user can lose lives in one directory: config.json, logs/ and the
default output/ folder. That directory is deliberately outside the application
folder, because a PyInstaller rebuild deletes dist/KluteTimer wholesale and used
to take the user's chosen output folder with it.

get_data_dir() never asks whether the build is frozen. The executable and a
source run resolve the same path by the same rule, so the code path the exe
takes is the code path the test suite covers.
"""
import os
import shutil
import sys

ENV_DATA_DIR = "KLUTE_TIMER_DATA_DIR"
APP_FOLDER_NAME = "KluteTimer"
CONFIG_NAME = "config.json"


def get_data_dir() -> str:
    """The directory holding config.json, logs/ and the default output/."""
    override = os.environ.get(ENV_DATA_DIR)
    if override:
        return os.path.abspath(override)

    # APPDATA is always set on Windows; the fallback keeps tests and any odd
    # environment from resolving to a bare relative path.
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_FOLDER_NAME)


def resource_path(*parts: str) -> str:
    """Path to a read-only bundled asset, such as the frontend UI.

    This one does branch on frozen, because bundled assets genuinely do live in
    two places: PyInstaller unpacks them to sys._MEIPASS, while a source
    checkout keeps them under the project root.
    """
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def get_legacy_dir() -> str:
    """Where config.json lived before it moved to the data directory.

    Read once at startup so an existing install carries its presets forward.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def migrate_legacy_config(data_dir: str, legacy_dir: str) -> bool:
    """Copy a pre-move config.json into the data directory. Returns whether it did.

    One shot: an existing config is never overwritten, so this is a no-op on
    every launch after the first.
    """
    if os.path.abspath(data_dir) == os.path.abspath(legacy_dir):
        return False

    target = os.path.join(data_dir, CONFIG_NAME)
    source = os.path.join(legacy_dir, CONFIG_NAME)
    if os.path.exists(target) or not os.path.isfile(source):
        return False

    os.makedirs(data_dir, exist_ok=True)
    shutil.copy2(source, target)
    return True
