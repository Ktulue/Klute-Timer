import json
import os
import pytest
from unittest.mock import patch, MagicMock
from src.app import Api


def _write_config(tmp_path, output_dir=None, presets=None):
    if presets is None:
        presets = [
            {"name": "Socials", "duration": 120, "output_file": "socials.txt"},
            {"name": "Intro", "duration": 300, "output_file": "intro.txt"},
            {"name": "Break", "duration": 600, "output_file": "break.txt"},
            {"name": "Custom", "duration": 0, "output_file": "custom.txt"},
        ]
    data = {
        "websocket": {"host": "127.0.0.1", "port": 8059, "auth": None},
        "default_finished_sound": None,
        "presets": presets,
        "window": {"minimize_to_tray": True},
    }
    if output_dir is not None:
        data["output_dir"] = str(output_dir)
    (tmp_path / "config.json").write_text(json.dumps(data))


@pytest.fixture
def api_factory(tmp_path, monkeypatch):
    """Builds an Api rooted at tmp_path, with the WebSocket client stubbed out."""

    def _build(output_dir=None, presets=None):
        monkeypatch.setattr("src.app.DATA_DIR", str(tmp_path))
        _write_config(tmp_path, output_dir=output_dir, presets=presets)
        with patch("src.app.StreamerbotClient"):
            return Api()

    return _build


class TestOutputFilesExistOnStartup:
    def test_creates_every_preset_file_on_startup(self, api_factory, tmp_path):
        out = tmp_path / "obs"
        api_factory(output_dir=out)

        for name in ("socials.txt", "intro.txt", "break.txt", "custom.txt"):
            assert (out / name).exists(), f"{name} was not created at startup"

    def test_created_files_start_empty(self, api_factory, tmp_path):
        out = tmp_path / "obs"
        api_factory(output_dir=out)

        assert (out / "socials.txt").read_text() == ""

    def test_creates_the_output_directory_if_missing(self, api_factory, tmp_path):
        out = tmp_path / "does-not-exist-yet"
        api_factory(output_dir=out)

        assert out.is_dir()

    def test_clears_a_stale_value_left_by_a_crash(self, api_factory, tmp_path):
        out = tmp_path / "obs"
        out.mkdir()
        (out / "socials.txt").write_text("02:34")

        api_factory(output_dir=out)

        assert (out / "socials.txt").read_text() == ""


class TestPathResolution:
    def test_resolves_preset_filename_against_output_dir(self, api_factory, tmp_path):
        out = tmp_path / "obs"
        api = api_factory(output_dir=out)

        paths = api.get_paths()
        assert paths["files"][0]["path"] == str(out / "socials.txt")

    def test_reports_every_preset_with_its_name(self, api_factory, tmp_path):
        api = api_factory(output_dir=tmp_path / "obs")

        paths = api.get_paths()
        assert [f["name"] for f in paths["files"]] == [
            "Socials",
            "Intro",
            "Break",
            "Custom",
        ]

    def test_reports_the_output_dir_as_an_absolute_path(self, api_factory, tmp_path):
        out = tmp_path / "obs"
        api = api_factory(output_dir=out)

        assert api.get_paths()["output_dir"] == str(out)

    def test_reports_the_log_dir(self, api_factory, tmp_path):
        api = api_factory(output_dir=tmp_path / "obs")

        assert api.get_paths()["log_dir"] == str(tmp_path / "logs")


class TestUnusableOutputDirFallsBack:
    def test_falls_back_when_the_output_dir_cannot_be_created(
        self, api_factory, tmp_path
    ):
        # A directory cannot be created underneath a regular file, so this
        # stands in for an unplugged drive or a revoked permission.
        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory")

        api = api_factory(output_dir=blocker / "sub")

        assert api.get_paths()["output_dir"] == str(tmp_path / "output")

    def test_still_creates_the_files_in_the_fallback_location(
        self, api_factory, tmp_path
    ):
        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory")

        api_factory(output_dir=blocker / "sub")

        assert (tmp_path / "output" / "socials.txt").exists()

    def test_warns_when_falling_back(self, api_factory, tmp_path, caplog):
        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory")

        api_factory(output_dir=blocker / "sub")

        assert any(
            "output" in r.message.lower() and r.levelname == "WARNING"
            for r in caplog.records
        )


class TestChangingTheOutputFolder:
    def test_creates_all_files_in_the_new_folder(self, api_factory, tmp_path):
        api = api_factory(output_dir=tmp_path / "before")
        new_dir = tmp_path / "after"
        api._window = MagicMock()
        api._window.create_file_dialog.return_value = (str(new_dir),)

        api.pick_output_dir()

        for name in ("socials.txt", "intro.txt", "break.txt", "custom.txt"):
            assert (new_dir / name).exists()

    def test_persists_the_new_folder_to_config(self, api_factory, tmp_path):
        api = api_factory(output_dir=tmp_path / "before")
        new_dir = tmp_path / "after"
        api._window = MagicMock()
        api._window.create_file_dialog.return_value = (str(new_dir),)

        api.pick_output_dir()

        saved = json.loads((tmp_path / "config.json").read_text())
        assert saved["output_dir"] == str(new_dir)

    def test_subsequent_writes_land_in_the_new_folder(self, api_factory, tmp_path):
        api = api_factory(output_dir=tmp_path / "before")
        new_dir = tmp_path / "after"
        api._window = MagicMock()
        api._window.create_file_dialog.return_value = (str(new_dir),)

        api.pick_output_dir()
        api._file_writer.write_time(0, "01:23")

        assert (new_dir / "socials.txt").read_text() == "01:23"

    def test_returns_the_updated_paths(self, api_factory, tmp_path):
        api = api_factory(output_dir=tmp_path / "before")
        new_dir = tmp_path / "after"
        api._window = MagicMock()
        api._window.create_file_dialog.return_value = (str(new_dir),)

        result = api.pick_output_dir()

        assert result["output_dir"] == str(new_dir)

    def test_cancelling_leaves_the_folder_unchanged(self, api_factory, tmp_path):
        out = tmp_path / "before"
        api = api_factory(output_dir=out)
        api._window = MagicMock()
        api._window.create_file_dialog.return_value = None

        result = api.pick_output_dir()

        assert result is None
        assert api.get_paths()["output_dir"] == str(out)


class TestFilenameCollision:
    def test_renaming_onto_another_presets_filename_does_not_raise(
        self, api_factory, tmp_path
    ):
        api = api_factory(output_dir=tmp_path / "obs")

        api.update_preset(1, {"output_file": "socials.txt"})

    def test_colliding_rename_is_rejected(self, api_factory, tmp_path):
        api = api_factory(output_dir=tmp_path / "obs")

        api.update_preset(1, {"output_file": "socials.txt"})

        assert api._config.presets[1].output_file == "intro.txt"

    def test_colliding_rename_warns(self, api_factory, tmp_path, caplog):
        api = api_factory(output_dir=tmp_path / "obs")

        api.update_preset(1, {"output_file": "socials.txt"})

        assert any(
            "socials.txt" in r.message and r.levelname == "WARNING"
            for r in caplog.records
        )

    def test_a_free_filename_is_accepted(self, api_factory, tmp_path):
        out = tmp_path / "obs"
        api = api_factory(output_dir=out)

        api.update_preset(1, {"output_file": "starting-soon.txt"})

        assert api._config.presets[1].output_file == "starting-soon.txt"
        assert (out / "starting-soon.txt").exists()


class TestOpeningFolders:
    def test_opens_the_output_folder(self, api_factory, tmp_path):
        out = tmp_path / "obs"
        api = api_factory(output_dir=out)

        with patch("src.app.os.startfile", create=True) as startfile:
            api.open_output_dir()

        startfile.assert_called_once_with(str(out))

    def test_opens_the_log_folder(self, api_factory, tmp_path):
        api = api_factory(output_dir=tmp_path / "obs")

        with patch("src.app.os.startfile", create=True) as startfile:
            api.open_log_dir()

        startfile.assert_called_once_with(str(tmp_path / "logs"))
