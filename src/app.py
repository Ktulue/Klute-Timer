# src/app.py
import os
import sys
import json
import webview
import threading
from typing import Optional

import pystray
from PIL import Image, ImageDraw

from src.config import Config
from src.timer import Timer
from src.file_writer import FileWriter
from src.sound_player import SoundPlayer
from src.ws_client import StreamerbotClient
from src.logger import setup_logger, get_logger


def get_base_dir() -> str:
    """Directory for user-writable files (config.json, output/, logs/, sounds/).

    In a frozen PyInstaller build these live next to the executable so the
    user can still edit presets and OBS can read the output files.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(*parts: str) -> str:
    """Path to a read-only bundled asset (e.g. the frontend/ UI).

    PyInstaller unpacks bundled data to sys._MEIPASS at runtime; in a normal
    source checkout the assets live under the project root instead.
    """
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


BASE_DIR = get_base_dir()
log = get_logger("app")


class Api:
    def __init__(self):
        self._window: Optional[webview.Window] = None
        self._config = Config(os.path.join(BASE_DIR, "config.json"))
        self._file_writer = FileWriter()
        self._sound_player = SoundPlayer()
        self._timers: list[Timer] = []
        self._ws_client: Optional[StreamerbotClient] = None
        self._ws_status = "disconnected"

        self._init_timers()
        self._init_ws_client()

    def set_window(self, window: webview.Window) -> None:
        self._window = window

    def _init_timers(self) -> None:
        for i, preset in enumerate(self._config.presets):
            self._file_writer.register(i, os.path.join(BASE_DIR, preset.output_file))
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

            self._config.update_preset(timer_id, updates)
            preset = self._config.presets[timer_id]
            timer = self._timers[timer_id]

            # Update live timer trigger config
            if "trigger_seconds" in updates:
                timer._trigger_seconds = updates["trigger_seconds"]
            if "trigger_action" in updates:
                timer._trigger_action = updates["trigger_action"]

            # Re-register file writer if output path changed
            if "output_file" in updates:
                self._file_writer.register(
                    timer_id, os.path.join(BASE_DIR, preset.output_file)
                )

            self._push_timer_update(timer_id)

    def pick_output_file(self, timer_id: int) -> Optional[str]:
        """Open a native Save-dialog file picker for the given preset's output file.

        Returns the chosen path on success, None on cancel or validation failure.
        Validation failures are logged at WARNING level so the user can check
        logs for the specific reason.
        """
        if not (0 <= timer_id < len(self._config.presets)):
            log.warning(
                f"pick_output_file: invalid timer_id {timer_id}",
                extra={"context": "pick_output_file", "state": f"num_presets={len(self._config.presets)}"},
            )
            return None

        if not self._window:
            log.warning(
                "pick_output_file: window not initialized",
                extra={"context": "pick_output_file", "state": "no window"},
            )
            return None

        # Open the native save dialog
        result = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            file_types=("Text Files (*.txt)", "All files (*.*)"),
            save_filename="timer_output.txt",
        )

        if not result:
            # User cancelled
            return None

        # create_file_dialog returns a tuple/list — take the first entry
        chosen_path = result[0] if isinstance(result, (list, tuple)) else result
        if not chosen_path:
            # Defensive: treat empty path as cancel even though no shipping
            # pywebview backend produces this. Avoids a silent fallback to
            # os.getcwd() in os.path.abspath('').
            return None
        normalized = os.path.normpath(os.path.abspath(chosen_path))

        # Validate: parent dir must exist and be writable
        parent_dir = os.path.dirname(normalized)
        if not os.path.isdir(parent_dir):
            log.warning(
                f"pick_output_file: parent directory does not exist: {parent_dir}",
                extra={"context": "pick_output_file", "state": f"path={normalized}"},
            )
            return None

        if not os.access(parent_dir, os.W_OK):
            log.warning(
                f"pick_output_file: parent directory not writable: {parent_dir}",
                extra={"context": "pick_output_file", "state": f"path={normalized}"},
            )
            return None

        # Check for collision with another preset's output_file
        for i, p in enumerate(self._config.presets):
            if i == timer_id:
                continue
            other = os.path.normpath(os.path.abspath(os.path.join(BASE_DIR, p.output_file)))
            if other == normalized:
                log.warning(
                    f"pick_output_file: path already used by preset {i} ({p.name})",
                    extra={"context": "pick_output_file", "state": f"path={normalized}"},
                )
                return None

        # All validation passed — apply the update via update_preset
        # (which handles file_writer re-registration)
        self.update_preset(timer_id, {"output_file": normalized})

        log.info(
            f"pick_output_file: timer {timer_id} output set to {normalized}",
            extra={"context": "pick_output_file", "state": "success"},
        )
        return normalized

    def get_presets(self) -> list[dict]:
        return [p.to_dict() for p in self._config.presets]

    def get_logs(self, severity: str = "INFO", count: int = 50) -> list[str]:
        log_path = os.path.join(BASE_DIR, "logs", "klute-timer.log")
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
    setup_logger(log_dir=os.path.join(BASE_DIR, "logs"))

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
