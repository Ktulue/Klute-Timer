import json
import os
import pytest
from unittest.mock import patch

from src.app import Api


def _write_config(path, output_dir=None):
    data = {
        "websocket": {"host": "127.0.0.1", "port": 8059, "auth": None},
        "default_finished_sound": None,
        "presets": [
            {"name": "Socials", "duration": 120, "output_file": "socials.txt"},
            {"name": "Intro", "duration": 300, "output_file": "intro.txt"},
            {"name": "Break", "duration": 600, "output_file": "break.txt"},
            {"name": "Custom", "duration": 0, "output_file": "custom.txt"},
        ],
        "window": {"minimize_to_tray": True},
    }
    if output_dir is not None:
        data["output_dir"] = str(output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


@pytest.fixture
def api_factory(tmp_path, monkeypatch):
    """Builds an Api rooted at a data directory, with no legacy config in sight."""

    def _build(output_dir=None, legacy_dir=None, write_config=True):
        data_dir = tmp_path / "data"
        data_dir.mkdir(exist_ok=True)
        monkeypatch.setattr("src.app.DATA_DIR", str(data_dir))
        monkeypatch.setattr(
            "src.app.get_legacy_dir", lambda: str(legacy_dir or tmp_path / "nothing")
        )
        if write_config:
            _write_config(data_dir / "config.json", output_dir=output_dir)
        with patch("src.app.StreamerbotClient"):
            return Api()

    return _build


class TestUserDataLivesInTheDataDir:
    def test_config_is_read_from_the_data_dir(self, api_factory, tmp_path):
        api = api_factory(output_dir=tmp_path / "obs")

        assert api._config._path == str(tmp_path / "data" / "config.json")

    def test_a_fresh_install_defaults_output_beside_the_config(
        self, api_factory, tmp_path
    ):
        api = api_factory(write_config=False)

        assert api.get_paths()["output_dir"] == str(tmp_path / "data" / "output")

    def test_a_fresh_install_writes_its_files_into_the_data_dir(
        self, api_factory, tmp_path
    ):
        api_factory(write_config=False)

        assert (tmp_path / "data" / "output" / "socials.txt").exists()


class TestLegacyConfigMigration:
    def test_a_config_left_beside_the_exe_is_adopted(self, api_factory, tmp_path):
        legacy = tmp_path / "old"
        _write_config(legacy / "config.json", output_dir=tmp_path / "Overlays")

        api = api_factory(legacy_dir=legacy, write_config=False)

        assert api.get_paths()["configured_output_dir"] == str(tmp_path / "Overlays")

    def test_an_existing_config_is_never_replaced_by_a_legacy_one(
        self, api_factory, tmp_path
    ):
        legacy = tmp_path / "old"
        _write_config(legacy / "config.json", output_dir=tmp_path / "stale")

        api = api_factory(
            legacy_dir=legacy, output_dir=tmp_path / "current", write_config=True
        )

        assert api.get_paths()["configured_output_dir"] == str(tmp_path / "current")


class TestDefaultVersusCustomLocation:
    def test_the_default_folder_is_reported_as_default(self, api_factory):
        api = api_factory(write_config=False)

        assert api.get_paths()["is_default_output_dir"] is True

    def test_a_chosen_folder_is_reported_as_custom(self, api_factory, tmp_path):
        api = api_factory(output_dir=tmp_path / "Overlays")

        assert api.get_paths()["is_default_output_dir"] is False


class TestResetOutputDirToDefault:
    def test_reset_points_output_back_at_the_data_dir(self, api_factory, tmp_path):
        api = api_factory(output_dir=tmp_path / "Overlays")

        result = api.reset_output_dir()

        assert result["output_dir"] == str(tmp_path / "data" / "output")

    def test_reset_recreates_the_timer_files_in_the_default_folder(
        self, api_factory, tmp_path
    ):
        api = api_factory(output_dir=tmp_path / "Overlays")

        api.reset_output_dir()

        for name in ("socials.txt", "intro.txt", "break.txt", "custom.txt"):
            assert (tmp_path / "data" / "output" / name).exists()

    def test_reset_survives_a_restart(self, api_factory, tmp_path):
        api = api_factory(output_dir=tmp_path / "Overlays")

        api.reset_output_dir()

        saved = json.loads((tmp_path / "data" / "config.json").read_text())
        assert saved["output_dir"] == str(tmp_path / "data" / "output")

    def test_reset_reports_the_default_location(self, api_factory, tmp_path):
        api = api_factory(output_dir=tmp_path / "Overlays")

        api.reset_output_dir()

        assert api.get_paths()["is_default_output_dir"] is True
