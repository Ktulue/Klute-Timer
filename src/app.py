# src/app.py
import os
import sys
import json
import webview
import threading
from typing import Optional

import pystray
from PIL import Image, ImageDraw

from src.config import Config, filename_only
from src.paths import get_data_dir, get_legacy_dir, migrate_legacy_config, resource_path
from src.timer import Timer
from src.file_writer import FileWriter
from src.sound_player import SoundPlayer
from src.ws_client import StreamerbotClient
from src.logger import setup_logger, get_logger


DATA_DIR = get_data_dir()
log = get_logger("app")


class Api:
    def __init__(self):
        self._window: Optional[webview.Window] = None
        # An install from before user data moved out of the app folder still has
        # its presets and chosen output folder beside the exe. Adopt them once,
        # before Config would otherwise write a fresh default over the top.
        if migrate_legacy_config(DATA_DIR, get_legacy_dir()):
            log.info(
                f"adopted existing config from {get_legacy_dir()}",
                extra={"context": "migrate", "state": f"data_dir={DATA_DIR}"},
            )
        self._config = Config(os.path.join(DATA_DIR, "config.json"))
        self._file_writer = FileWriter()
        self._sound_player = SoundPlayer()
        self._timers: list[Timer] = []
        self._ws_client: Optional[StreamerbotClient] = None
        self._ws_status = "disconnected"

        self._init_timers()
        self._init_ws_client()

    def set_window(self, window: webview.Window) -> None:
        self._window = window

    def _resolve_output_dir(self) -> str:
        """The directory timer files are actually written to.

        Falls back to <DATA_DIR>/output when the configured directory can't be
        used — an unplugged drive or a revoked permission must not take the app
        down mid-stream. The fallback is deliberately not written back to the
        config: the stored path is the user's intent, and it may well be valid
        again next launch.
        """
        configured = self._config.output_dir
        try:
            os.makedirs(configured, exist_ok=True)
            if os.access(configured, os.W_OK):
                return configured
            reason = "not writable"
        except OSError as e:
            reason = str(e)

        fallback = os.path.join(DATA_DIR, "output")
        log.warning(
            f"configured output folder unusable ({reason}); using {fallback}",
            extra={"context": "resolve_output_dir", "state": f"configured={configured}"},
        )
        os.makedirs(fallback, exist_ok=True)
        return fallback

    def _output_path(self, timer_id: int) -> str:
        preset = self._config.presets[timer_id]
        return os.path.join(self._resolve_output_dir(), preset.output_file)

    def _register_all_outputs(self) -> None:
        """Point every timer at its file and make sure that file exists.

        The empty write is what actually creates the file on disk, so OBS can be
        aimed at it before the timer has ever run. It also wipes any stale value
        a crash or a kill left behind on the last run.
        """
        # Resolved once rather than per preset, so an unusable folder warns a
        # single time instead of once per timer.
        output_dir = self._resolve_output_dir()
        for i, preset in enumerate(self._config.presets):
            self._file_writer.register(i, os.path.join(output_dir, preset.output_file))
            self._file_writer.clear(i)

    def _init_timers(self) -> None:
        self._register_all_outputs()
        for i, preset in enumerate(self._config.presets):
            timer = Timer(
                timer_id=i,
                duration=preset.duration,
                trigger_seconds=preset.trigger_seconds,
                trigger_action=preset.trigger_action,
                on_tick=self._on_tick,
                on_finish=self._on_finish,
                on_trigger=self._on_trigger,
                on_blank=self._on_blank,
            )
            self._timers.append(timer)

    def _init_ws_client(self) -> None:
        self._ws_client = StreamerbotClient(
            host=self._config.ws_host,
            port=self._config.ws_port,
            on_command=self._on_ws_command,
            on_status_change=self._on_ws_status_change,
        )

    def _on_tick(self, timer_id: int, remaining: int) -> None:
        timer = self._timers[timer_id]
        formatted = timer.format_remaining()
        self._file_writer.write_time(timer_id, formatted)
        self._push_timer_update(timer_id)

    def _on_finish(self, timer_id: int) -> None:
        # Note on OBS file state: the OBS output file should contain "00:00" at
        # this moment. We don't write it here — _on_tick wrote it on the final
        # decrement (when remaining hit 0) just before the timer thread fired
        # this callback. The file holds that value through the finishing-state
        # hold until _on_blank clears it.
        preset = self._config.presets[timer_id]
        # Fallback semantics: None on either field means "use the next level."
        # Empty string ("") is also treated as falsy and falls through to the
        # global default — this is the Python `or` operator's behavior and is
        # intentional. If a future feature wants "explicitly no sound for this
        # preset," it should be expressed via a sentinel value or a separate
        # boolean field, not by writing "" to finished_sound.
        sound = preset.finished_sound or self._config.default_finished_sound
        self._sound_player.play(sound)
        self._push_timer_update(timer_id)

    def _on_blank(self, timer_id: int) -> None:
        self._file_writer.clear(timer_id)
        self._push_timer_update(timer_id)

    def _on_trigger(self, timer_id: int, action_name: str) -> None:
        if self._ws_client:
            self._ws_client.trigger_action(action_name)

    def _on_ws_command(self, command: dict) -> None:
        cmd = command["command"]
        timer_idx = command["timer"] - 1  # Convert 1-based to 0-based

        if timer_idx < 0 or timer_idx >= len(self._timers):
            log.warning(
                f"invalid timer index: {command['timer']}",
                extra={
                    "context": f"ws command: {cmd}",
                    "state": f"num_timers={len(self._timers)}",
                },
            )
            return

        timer = self._timers[timer_idx]

        if cmd == "start":
            duration = command.get("duration")
            timer.start(override_duration=duration)
        elif cmd == "pause":
            timer.toggle_pause()
        elif cmd == "stop":
            timer.stop()
            self._file_writer.clear(timer_idx)

        self._push_timer_update(timer_idx)

    def _on_ws_status_change(self, status: str) -> None:
        self._ws_status = status
        self._push_ws_status()

    def _push_timer_update(self, timer_id: int) -> None:
        if not self._window:
            return
        state = self._get_timer_state(timer_id)
        js = f"window.onTimerUpdate({json.dumps(state)})"
        self._window.evaluate_js(js)

    def _push_ws_status(self) -> None:
        if not self._window:
            return
        js = f"window.onWsStatusUpdate({json.dumps(self._ws_status)})"
        self._window.evaluate_js(js)

    def _get_timer_state(self, timer_id: int) -> dict:
        timer = self._timers[timer_id]
        preset = self._config.presets[timer_id]
        return {
            "id": timer_id,
            "name": preset.name,
            "state": timer.state,
            "remaining": timer.remaining,
            "formatted": timer.format_remaining(),
            "duration": timer.duration,
        }

    # --- JS Bridge Methods ---

    def get_state(self) -> dict:
        return {
            "timers": [self._get_timer_state(i) for i in range(len(self._timers))],
            "ws_status": self._ws_status,
        }

    def start_timer(self, timer_id: int, duration: Optional[int] = None) -> None:
        if 0 <= timer_id < len(self._timers):
            self._timers[timer_id].start(override_duration=duration)
            self._push_timer_update(timer_id)

    def pause_timer(self, timer_id: int) -> None:
        if 0 <= timer_id < len(self._timers):
            self._timers[timer_id].toggle_pause()
            self._push_timer_update(timer_id)

    def stop_timer(self, timer_id: int) -> None:
        if 0 <= timer_id < len(self._timers):
            self._timers[timer_id].stop()
            self._file_writer.clear(timer_id)
            self._push_timer_update(timer_id)

    def update_preset(self, timer_id: int, updates: dict) -> None:
        if 0 <= timer_id < len(self._config.presets):
            # end_message feature is paused — drop any attempted updates (WARNING is logged)
            if "end_message" in updates:
                log.warning(
                    "end_message updates are paused; ignoring",
                    extra={"context": "update_preset", "state": f"timer_id={timer_id}"},
                )
                updates = {k: v for k, v in updates.items() if k != "end_message"}

            # Two presets sharing one file would have them overwrite each other,
            # so reject the rename before it reaches the config rather than
            # letting FileWriter.register raise across the JS bridge.
            if "output_file" in updates:
                requested = filename_only(updates["output_file"])
                taken = {
                    p.output_file
                    for i, p in enumerate(self._config.presets)
                    if i != timer_id
                }
                if requested in taken:
                    log.warning(
                        f"output filename '{requested}' is already used by another timer; ignoring",
                        extra={"context": "update_preset", "state": f"timer_id={timer_id}"},
                    )
                    updates = {k: v for k, v in updates.items() if k != "output_file"}
                else:
                    updates = {**updates, "output_file": requested}

            self._config.update_preset(timer_id, updates)
            timer = self._timers[timer_id]

            # Update live timer trigger config
            if "trigger_seconds" in updates:
                timer._trigger_seconds = updates["trigger_seconds"]
            if "trigger_action" in updates:
                timer._trigger_action = updates["trigger_action"]

            # Re-register file writer if the output filename changed
            if "output_file" in updates:
                self._file_writer.register(timer_id, self._output_path(timer_id))
                self._file_writer.clear(timer_id)

            self._push_timer_update(timer_id)

    def get_presets(self) -> list[dict]:
        return [p.to_dict() for p in self._config.presets]

    def get_paths(self) -> dict:
        """Every location the app reads or writes, for the settings panel.

        Reports where files are actually going, not merely what the config
        requested, so a fallback is visible rather than a mystery.
        """
        output_dir = self._resolve_output_dir()
        return {
            "output_dir": output_dir,
            "configured_output_dir": self._config.output_dir,
            "using_fallback": output_dir != self._config.output_dir,
            "is_default_output_dir": (
                self._config.output_dir == self._config.default_output_dir
            ),
            "log_dir": os.path.join(DATA_DIR, "logs"),
            "files": [
                {
                    "name": preset.name,
                    "filename": preset.output_file,
                    "path": os.path.join(output_dir, preset.output_file),
                }
                for preset in self._config.presets
            ],
        }

    def pick_output_dir(self) -> Optional[dict]:
        """Open a native folder picker for the shared timer output folder.

        Returns the updated paths on success, None on cancel or if the chosen
        folder can't be written to.
        """
        if not self._window:
            log.warning(
                "pick_output_dir: window not initialized",
                extra={"context": "pick_output_dir", "state": "no window"},
            )
            return None

        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if not result:
            return None

        chosen = result[0] if isinstance(result, (list, tuple)) else result
        if not chosen:
            return None
        normalized = os.path.normpath(os.path.abspath(chosen))

        try:
            os.makedirs(normalized, exist_ok=True)
        except OSError as e:
            log.warning(
                f"pick_output_dir: cannot create {normalized}: {e}",
                extra={"context": "pick_output_dir", "state": "makedirs failed"},
            )
            return None

        if not os.access(normalized, os.W_OK):
            log.warning(
                f"pick_output_dir: folder not writable: {normalized}",
                extra={"context": "pick_output_dir", "state": "not writable"},
            )
            return None

        self._config.output_dir = normalized
        self._config.save()
        # Files at the old location are deliberately left alone rather than
        # moved: OBS may still be reading them, and silently relocating a source
        # out from under it is worse than leaving a stray file behind.
        self._register_all_outputs()

        log.info(
            f"output folder changed to {normalized}",
            extra={"context": "pick_output_dir", "state": "success"},
        )
        return self.get_paths()

    def reset_output_dir(self) -> dict:
        """Send the timer files back to the default folder in the data directory.

        Same relocation as picking a folder, so the old files are left where
        they are rather than moved out from under OBS.
        """
        self._config.output_dir = self._config.default_output_dir
        self._config.save()
        self._register_all_outputs()

        log.info(
            f"output folder reset to {self._config.output_dir}",
            extra={"context": "reset_output_dir", "state": "success"},
        )
        return self.get_paths()

    def open_output_dir(self) -> bool:
        return self._open_folder(self._resolve_output_dir())

    def open_log_dir(self) -> bool:
        return self._open_folder(os.path.join(DATA_DIR, "logs"))

    def _open_folder(self, path: str) -> bool:
        try:
            os.makedirs(path, exist_ok=True)
            os.startfile(path)
            return True
        except OSError as e:
            log.error(
                f"failed to open folder {path}: {e}",
                extra={"context": "open_folder", "state": f"path={path}"},
            )
            return False

    def get_logs(self, severity: str = "INFO", count: int = 50) -> list[str]:
        log_path = os.path.join(DATA_DIR, "logs", "klute-timer.log")
        if not os.path.exists(log_path):
            return []
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if severity != "ALL":
            severity_levels = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}
            min_level = severity_levels.get(severity, 0)
            lines = [
                l for l in lines
                if any(f"| {lvl} |" in l for lvl, v in severity_levels.items() if v >= min_level)
            ]
        return lines[-count:]


def start_backend(window: webview.Window, api: Api) -> None:
    api.set_window(window)
    if api._ws_client:
        api._ws_client.start()

    log.info(
        "app started",
        extra={"context": "startup", "state": "running"},
    )


def create_tray_icon() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([8, 8, 56, 56], fill=(45, 212, 191))
    draw.text((22, 18), "K", fill=(13, 17, 23))
    return img


def main() -> None:
    setup_logger(log_dir=os.path.join(DATA_DIR, "logs"))

    api = Api()

    frontend_path = resource_path("frontend", "index.html")

    window = webview.create_window(
        "Klute Timer",
        frontend_path,
        js_api=api,
        width=800,
        height=600,
        min_size=(600, 400),
    )

    tray_icon = None

    def show_window():
        window.show()
        window.restore()

    def quit_app(icon, item):
        icon.stop()
        for timer in api._timers:
            timer.stop()
        for i in range(len(api._timers)):
            api._file_writer.clear(i)
        if api._ws_client:
            api._ws_client.stop()
        window.destroy()

    def on_closing():
        if api._config.minimize_to_tray:
            window.hide()
            return False  # Prevent actual close
        # Clean shutdown
        for timer in api._timers:
            timer.stop()
        for i in range(len(api._timers)):
            api._file_writer.clear(i)
        if api._ws_client:
            api._ws_client.stop()
        if tray_icon:
            tray_icon.stop()
        log.info(
            "app closing",
            extra={"context": "shutdown", "state": "closing"},
        )

    window.events.closing += on_closing

    tray_icon = pystray.Icon(
        "klute-timer",
        create_tray_icon(),
        "Klute Timer",
        menu=pystray.Menu(
            pystray.MenuItem("Show", lambda icon, item: show_window(), default=True),
            pystray.MenuItem("Quit", quit_app),
        ),
    )

    tray_thread = threading.Thread(target=tray_icon.run, daemon=True)
    tray_thread.start()

    webview.start(start_backend, (window, api), debug=False)


if __name__ == "__main__":
    main()
