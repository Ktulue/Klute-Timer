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
