import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional


def filename_only(path: str) -> str:
    """Reduce a stored output path to its bare filename.

    Timer output files used to carry a full path each; they now live together
    in Config.output_dir and store only a filename. Both separators are handled
    so a config written before that change migrates cleanly.
    """
    return path.replace("\\", "/").rsplit("/", 1)[-1]


@dataclass
class PresetConfig:
    name: str
    duration: int
    end_message: str = ""
    trigger_seconds: Optional[int] = None
    trigger_action: Optional[str] = None
    output_file: str = ""
    finished_sound: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


DEFAULT_PRESETS = [
    PresetConfig(
        name="Socials",
        duration=120,
        end_message="",
        trigger_seconds=30,
        trigger_action="Push The Button Reminder",
        output_file="socials.txt",
    ),
    PresetConfig(
        name="Intro",
        duration=300,
        end_message="",
        trigger_seconds=None,
        trigger_action=None,
        output_file="intro.txt",
    ),
    PresetConfig(
        name="Break",
        duration=600,
        end_message="",
        trigger_seconds=None,
        trigger_action=None,
        output_file="break.txt",
    ),
    PresetConfig(
        name="Custom",
        duration=0,
        end_message="",
        trigger_seconds=None,
        trigger_action=None,
        output_file="custom.txt",
    ),
]


class Config:
    def __init__(self, config_path: str = "config.json"):
        self._path = config_path
        # Timer output files default to an "output" folder beside config.json,
        # which puts them next to the executable in a frozen build. Stored as an
        # absolute path so the user can read it straight out of the settings
        # panel, and so rebuilding or moving the app never silently relocates
        # the files OBS is reading.
        self._default_output_dir = os.path.abspath(
            os.path.join(os.path.dirname(config_path) or ".", "output")
        )
        self.ws_host: str = "127.0.0.1"
        self.ws_port: int = 8059
        self.ws_auth: Optional[str] = None
        self.default_finished_sound: Optional[str] = None
        self.output_dir: str = self._default_output_dir
        self.presets: list[PresetConfig] = []
        self.minimize_to_tray: bool = True

        if os.path.exists(self._path):
            self._load()
        else:
            self._set_defaults()
            self.save()

    def _set_defaults(self) -> None:
        self.ws_host = "127.0.0.1"
        self.ws_port = 8059
        self.ws_auth = None
        self.default_finished_sound = None
        self.output_dir = self._default_output_dir
        self.presets = [
            PresetConfig(**asdict(p)) for p in DEFAULT_PRESETS
        ]
        self.minimize_to_tray = True

    def _load(self) -> None:
        with open(self._path, "r", encoding="utf-8") as f:
            data = json.load(f)

        ws = data.get("websocket", {})
        self.ws_host = ws.get("host", "127.0.0.1")
        self.ws_port = ws.get("port", 8059)
        self.ws_auth = ws.get("auth", None)

        self.default_finished_sound = data.get("default_finished_sound", None)

        # A config written before output_dir existed has no such key; fall back
        # to the default rather than leaving it unset.
        self.output_dir = data.get("output_dir") or self._default_output_dir

        self.presets = [
            PresetConfig(**p) for p in data.get("presets", [])
        ]
        for preset in self.presets:
            preset.output_file = filename_only(preset.output_file)

        window = data.get("window", {})
        self.minimize_to_tray = window.get("minimize_to_tray", True)

    def save(self) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        data = {
            "websocket": {
                "host": self.ws_host,
                "port": self.ws_port,
                "auth": self.ws_auth,
            },
            "default_finished_sound": self.default_finished_sound,
            "output_dir": self.output_dir,
            "presets": [p.to_dict() for p in self.presets],
            "window": {
                "minimize_to_tray": self.minimize_to_tray,
            },
        }
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def update_preset(self, index: int, updates: dict) -> None:
        preset = self.presets[index]
        for key, value in updates.items():
            if hasattr(preset, key):
                setattr(preset, key, value)
        self.save()
