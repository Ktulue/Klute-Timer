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
from src.ws_client import StreamerbotClient
from src.logger import setup_logger, get_logger


def get_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE_DIR = get_base_dir()
log = get_logger("app")


class Api:
    def __init__(self):
        self._window: Optional[webview.Window] = None
        self._config = Config(os.path.join(BASE_DIR, "config.json"))
        self._file_writer = FileWriter()
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
        preset = self._config.presets[timer_id]
        self._file_writer.write_end_message(timer_id, preset.end_message)
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

    def reset_timer(self, timer_id: int) -> None:
        if 0 <= timer_id < len(self._timers):
            self._timers[timer_id].reset()
            self._push_timer_update(timer_id)

    def update_preset(self, timer_id: int, updates: dict) -> None:
        if 0 <= timer_id < len(self._config.presets):
            self._config.update_preset(timer_id, updates)
            preset = self._config.presets[timer_id]

            # Re-register file writer if output path changed
            if "output_file" in updates:
                self._file_writer.register(
                    timer_id, os.path.join(BASE_DIR, preset.output_file)
                )

            self._push_timer_update(timer_id)

    def get_presets(self) -> list[dict]:
        return [p.to_dict() for p in self._config.presets]

    def get_logs(self, severity: str = "INFO", count: int = 50) -> list[str]:
        log_path = os.path.join(BASE_DIR, "logs", "klute-timer.log")
        if not os.path.exists(log_path):
            return []
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if severity != "ALL":
            lines = [l for l in lines if f"| {severity} |" in l or "| ERROR |" in l]
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

    frontend_path = os.path.join(BASE_DIR, "frontend", "index.html")

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
