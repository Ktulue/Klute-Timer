import os
import json
import pytest
from unittest.mock import patch
from src.app import Api


@pytest.fixture
def configured_api(tmp_path, monkeypatch):
    monkeypatch.setattr("src.app.DATA_DIR", str(tmp_path))
    config_data = {
        "websocket": {"host": "127.0.0.1", "port": 8059, "auth": None},
        "default_finished_sound": None,
        "presets": [
            {
                "name": "Test",
                "duration": 60,
                "end_message": "original",
                "trigger_seconds": None,
                "trigger_action": None,
                "output_file": "output/test.txt",
                "finished_sound": None,
            }
        ],
        "window": {"minimize_to_tray": True},
    }
    (tmp_path / "config.json").write_text(json.dumps(config_data))
    os.makedirs(tmp_path / "output", exist_ok=True)
    with patch("src.app.StreamerbotClient"):
        yield Api()


class TestUpdatePresetEndMessageFilter:
    def test_update_preset_drops_end_message_key(self, configured_api, caplog):
        api = configured_api

        # Try to update end_message — should be dropped
        api.update_preset(0, {"end_message": "new value", "name": "Updated"})

        # Name update should have applied; end_message should NOT have changed
        assert api._config.presets[0].name == "Updated"
        assert api._config.presets[0].end_message == "original"
        # And there should be a warning log about the dropped key
        assert any(
            "end_message" in r.message and ("paused" in r.message.lower() or "ignor" in r.message.lower())
            for r in caplog.records
        )

    def test_update_preset_with_only_end_message_does_not_raise(self, configured_api):
        api = configured_api

        # Calling update_preset with ONLY end_message should not raise
        # (the filter empties the dict, and Config.update_preset must accept {})
        api.update_preset(0, {"end_message": "should be dropped"})

        # end_message must be unchanged
        assert api._config.presets[0].end_message == "original"
        # Other fields must be unchanged too
        assert api._config.presets[0].name == "Test"
        assert api._config.presets[0].duration == 60

    def test_update_preset_without_end_message_does_not_log_warning(self, configured_api, caplog):
        api = configured_api

        api.update_preset(0, {"name": "Renamed"})

        # The name update should have applied
        assert api._config.presets[0].name == "Renamed"
        # No "end_message" warning should have been logged
        assert not any(
            "end_message" in r.message and ("paused" in r.message.lower() or "ignor" in r.message.lower())
            for r in caplog.records
        )
