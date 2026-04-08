import json
from src.config import Config, PresetConfig, DEFAULT_PRESETS


class TestConfigDefaults:
    def test_creates_default_config_file(self, tmp_path):
        config_path = tmp_path / "config.json"
        config = Config(str(config_path))
        assert config_path.exists()

    def test_default_websocket_settings(self, tmp_path):
        config = Config(str(tmp_path / "config.json"))
        assert config.ws_host == "127.0.0.1"
        assert config.ws_port == 8059
        assert config.ws_auth is None

    def test_default_presets(self, tmp_path):
        config = Config(str(tmp_path / "config.json"))
        assert len(config.presets) == 4
        assert config.presets[0].name == "Socials"
        assert config.presets[0].duration == 120
        assert config.presets[0].trigger_seconds == 30
        assert config.presets[1].name == "Intro"
        assert config.presets[1].duration == 300
        assert config.presets[2].name == "Break"
        assert config.presets[2].duration == 600
        assert config.presets[3].name == "Custom"
        assert config.presets[3].duration == 0

    def test_default_window_settings(self, tmp_path):
        config = Config(str(tmp_path / "config.json"))
        assert config.minimize_to_tray is True


class TestConfigPersistence:
    def test_save_and_reload(self, tmp_path):
        config_path = str(tmp_path / "config.json")
        config = Config(config_path)
        config.presets[0].duration = 180
        config.presets[0].name = "Cheers"
        config.save()

        config2 = Config(config_path)
        assert config2.presets[0].duration == 180
        assert config2.presets[0].name == "Cheers"

    def test_loads_existing_config(self, tmp_path):
        config_path = tmp_path / "config.json"
        data = {
            "websocket": {"host": "192.168.1.10", "port": 9090, "auth": "secret"},
            "presets": [
                {
                    "name": "Test",
                    "duration": 60,
                    "end_message": "Done!",
                    "trigger_seconds": 10,
                    "trigger_action": "MyAction",
                    "output_file": "output/test.txt",
                }
            ],
            "window": {"minimize_to_tray": False},
        }
        config_path.write_text(json.dumps(data))
        config = Config(str(config_path))
        assert config.ws_host == "192.168.1.10"
        assert config.ws_port == 9090
        assert config.ws_auth == "secret"
        assert len(config.presets) == 1
        assert config.presets[0].name == "Test"
        assert config.minimize_to_tray is False


class TestPresetConfig:
    def test_preset_to_dict(self):
        preset = PresetConfig(
            name="Socials",
            duration=120,
            end_message="",
            trigger_seconds=30,
            trigger_action="Push The Button Reminder",
            output_file="output/socials.txt",
        )
        d = preset.to_dict()
        assert d["name"] == "Socials"
        assert d["duration"] == 120
        assert d["trigger_seconds"] == 30

    def test_update_preset(self, tmp_path):
        config = Config(str(tmp_path / "config.json"))
        config.update_preset(0, {"name": "Cheers", "duration": 90})
        assert config.presets[0].name == "Cheers"
        assert config.presets[0].duration == 90
        # unchanged fields stay the same
        assert config.presets[0].trigger_seconds == 30


class TestConfigFinishedSound:
    def test_preset_finished_sound_defaults_to_none(self, tmp_path):
        config = Config(str(tmp_path / "config.json"))
        for preset in config.presets:
            assert preset.finished_sound is None

    def test_default_finished_sound_defaults_to_none_when_missing(self, tmp_path):
        config_path = tmp_path / "config.json"
        data = {
            "websocket": {"host": "127.0.0.1", "port": 8059, "auth": None},
            "presets": [
                {
                    "name": "Test",
                    "duration": 60,
                    "end_message": "",
                    "trigger_seconds": None,
                    "trigger_action": None,
                    "output_file": "output/test.txt",
                }
            ],
            "window": {"minimize_to_tray": True},
        }
        config_path.write_text(json.dumps(data))
        config = Config(str(config_path))
        assert config.default_finished_sound is None

    def test_default_finished_sound_loads_from_file(self, tmp_path):
        config_path = tmp_path / "config.json"
        data = {
            "websocket": {"host": "127.0.0.1", "port": 8059, "auth": None},
            "default_finished_sound": "C:\\Windows\\Media\\chimes.wav",
            "presets": [],
            "window": {"minimize_to_tray": True},
        }
        config_path.write_text(json.dumps(data))
        config = Config(str(config_path))
        assert config.default_finished_sound == "C:\\Windows\\Media\\chimes.wav"

    def test_preset_finished_sound_loads_from_file(self, tmp_path):
        config_path = tmp_path / "config.json"
        data = {
            "websocket": {"host": "127.0.0.1", "port": 8059, "auth": None},
            "presets": [
                {
                    "name": "Test",
                    "duration": 60,
                    "end_message": "",
                    "trigger_seconds": None,
                    "trigger_action": None,
                    "output_file": "output/test.txt",
                    "finished_sound": "sounds/custom.wav",
                }
            ],
            "window": {"minimize_to_tray": True},
        }
        config_path.write_text(json.dumps(data))
        config = Config(str(config_path))
        assert config.presets[0].finished_sound == "sounds/custom.wav"

    def test_default_finished_sound_persists_via_save(self, tmp_path):
        config_path = str(tmp_path / "config.json")
        config = Config(config_path)
        config.default_finished_sound = "sounds/global.wav"
        config.save()

        config2 = Config(config_path)
        assert config2.default_finished_sound == "sounds/global.wav"
