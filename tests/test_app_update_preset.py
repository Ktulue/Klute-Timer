import os
import json
from unittest.mock import patch
from src.app import Api


class TestUpdatePresetEndMessageFilter:
    def test_update_preset_drops_end_message_key(self, tmp_path, caplog, monkeypatch):
        # Point Api at a tmp config so it doesn't touch the real config.json
        monkeypatch.setattr("src.app.BASE_DIR", str(tmp_path))

        # Build a minimal config.json in the tmp dir
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
            api = Api()

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
