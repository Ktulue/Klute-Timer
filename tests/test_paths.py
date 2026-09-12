import os
import sys
import pytest

from src.paths import (
    ENV_DATA_DIR,
    get_data_dir,
    get_legacy_dir,
    migrate_legacy_config,
    resource_path,
)


class TestDataDirResolution:
    def test_environment_override_wins(self, tmp_path, monkeypatch):
        monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path / "chosen"))

        assert get_data_dir() == str(tmp_path / "chosen")

    def test_defaults_to_appdata_subfolder(self, tmp_path, monkeypatch):
        monkeypatch.delenv(ENV_DATA_DIR, raising=False)
        monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))

        assert get_data_dir() == os.path.join(str(tmp_path / "Roaming"), "KluteTimer")

    def test_falls_back_to_home_when_appdata_is_missing(self, tmp_path, monkeypatch):
        monkeypatch.delenv(ENV_DATA_DIR, raising=False)
        monkeypatch.delenv("APPDATA", raising=False)
        monkeypatch.setattr(os.path, "expanduser", lambda p: str(tmp_path / "home"))

        assert get_data_dir() == os.path.join(str(tmp_path / "home"), "KluteTimer")

    def test_resolves_a_relative_override_to_an_absolute_path(self, monkeypatch):
        monkeypatch.setenv(ENV_DATA_DIR, "relative-data")

        assert os.path.isabs(get_data_dir())

    def test_an_empty_override_is_ignored(self, tmp_path, monkeypatch):
        monkeypatch.setenv(ENV_DATA_DIR, "")
        monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))

        assert get_data_dir() == os.path.join(str(tmp_path / "Roaming"), "KluteTimer")

    def test_frozen_builds_and_source_runs_resolve_identically(self, tmp_path, monkeypatch):
        monkeypatch.delenv(ENV_DATA_DIR, raising=False)
        monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
        from_source = get_data_dir()

        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(tmp_path / "dist" / "KluteTimer.exe"))

        assert get_data_dir() == from_source


class TestLegacyDir:
    def test_frozen_build_looks_beside_the_executable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(tmp_path / "dist" / "KluteTimer.exe"))

        assert get_legacy_dir() == str(tmp_path / "dist")

    def test_source_run_looks_at_the_project_root(self, monkeypatch):
        monkeypatch.delattr(sys, "frozen", raising=False)
        expected = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        assert get_legacy_dir() == expected


class TestConfigMigration:
    def test_copies_a_legacy_config_into_the_data_dir(self, tmp_path):
        legacy = tmp_path / "old"
        legacy.mkdir()
        (legacy / "config.json").write_text('{"output_dir": "C:/Streaming/Overlays"}')
        data = tmp_path / "new"

        migrate_legacy_config(str(data), str(legacy))

        assert (data / "config.json").read_text() == '{"output_dir": "C:/Streaming/Overlays"}'

    def test_reports_that_it_migrated(self, tmp_path):
        legacy = tmp_path / "old"
        legacy.mkdir()
        (legacy / "config.json").write_text("{}")

        assert migrate_legacy_config(str(tmp_path / "new"), str(legacy)) is True

    def test_never_overwrites_an_existing_config(self, tmp_path):
        legacy = tmp_path / "old"
        legacy.mkdir()
        (legacy / "config.json").write_text('{"output_dir": "stale"}')
        data = tmp_path / "new"
        data.mkdir()
        (data / "config.json").write_text('{"output_dir": "current"}')

        migrated = migrate_legacy_config(str(data), str(legacy))

        assert migrated is False
        assert (data / "config.json").read_text() == '{"output_dir": "current"}'

    def test_does_nothing_when_there_is_no_legacy_config(self, tmp_path):
        legacy = tmp_path / "old"
        legacy.mkdir()
        data = tmp_path / "new"

        assert migrate_legacy_config(str(data), str(legacy)) is False
        assert not (data / "config.json").exists()

    def test_does_nothing_when_the_legacy_dir_is_the_data_dir(self, tmp_path):
        data = tmp_path / "same"
        data.mkdir()
        (data / "config.json").write_text("{}")

        assert migrate_legacy_config(str(data), str(data)) is False

    def test_creates_the_data_dir_when_migrating(self, tmp_path):
        legacy = tmp_path / "old"
        legacy.mkdir()
        (legacy / "config.json").write_text("{}")
        data = tmp_path / "deep" / "new"

        migrate_legacy_config(str(data), str(legacy))

        assert data.is_dir()

    def test_survives_an_unreadable_legacy_dir(self, tmp_path):
        data = tmp_path / "new"

        assert migrate_legacy_config(str(data), str(tmp_path / "nope")) is False


class TestResourcePath:
    def test_source_run_resolves_against_the_project_root(self, monkeypatch):
        monkeypatch.delattr(sys, "frozen", raising=False)
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        assert resource_path("frontend", "index.html") == os.path.join(
            root, "frontend", "index.html"
        )

    def test_frozen_build_resolves_against_the_unpacked_bundle(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False)

        assert resource_path("frontend", "index.html") == os.path.join(
            str(tmp_path / "bundle"), "frontend", "index.html"
        )

    def test_frozen_build_without_a_bundle_falls_back_beside_the_exe(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
        monkeypatch.setattr(sys, "executable", str(tmp_path / "dist" / "KluteTimer.exe"))

        assert resource_path("frontend") == os.path.join(str(tmp_path / "dist"), "frontend")

    def test_bundled_assets_are_not_the_user_data_dir(self, tmp_path, monkeypatch):
        """Read-only bundle and user-writable data must never resolve alike."""
        monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path / "data"))
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False)

        assert resource_path("frontend") != get_data_dir()
