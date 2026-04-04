import threading
import time
from typing import Optional, Callable

from src.logger import get_logger

log = get_logger("timer")


class Timer:
    def __init__(
        self,
        timer_id: int,
        duration: int,
        trigger_seconds: Optional[int] = None,
        trigger_action: Optional[str] = None,
        on_tick: Optional[Callable[[int, int], None]] = None,
        on_finish: Optional[Callable[[int], None]] = None,
        on_trigger: Optional[Callable[[int, str], None]] = None,
    ):
        self._id = timer_id
        self._duration = duration
        self._remaining = duration
        self._use_hms = duration >= 3600
        self._trigger_seconds = trigger_seconds
        self._trigger_action = trigger_action
        self._trigger_fired = False
        self._on_tick = on_tick
        self._on_finish = on_finish
        self._on_trigger = on_trigger
        self._state = "idle"
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def remaining(self) -> int:
        with self._lock:
            return self._remaining

    @property
    def timer_id(self) -> int:
        return self._id

    @property
    def duration(self) -> int:
        return self._duration

    def format_remaining(self) -> str:
        with self._lock:
            secs = self._remaining
        if self._use_hms:
            h = secs // 3600
            m = (secs % 3600) // 60
            s = secs % 60
            return f"{h:02d}:{m:02d}:{s:02d}"
        else:
            m = secs // 60
            s = secs % 60
            return f"{m:02d}:{s:02d}"

    def start(self, override_duration: Optional[int] = None) -> None:
        with self._lock:
            if self._state == "running":
                return
            if override_duration is not None:
                self._duration = override_duration
                self._use_hms = override_duration >= 3600
            self._remaining = self._duration
            self._trigger_fired = False
            self._state = "running"
            self._stop_event.clear()

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        log.info(
            f"timer {self._id} started ({self._duration}s)",
            extra={"context": "start", "state": f"remaining={self._remaining}"},
        )

    def pause(self) -> None:
        with self._lock:
            if self._state != "running":
                return
            self._state = "paused"
            self._stop_event.set()
        log.info(
            f"timer {self._id} paused",
            extra={"context": "pause", "state": f"remaining={self._remaining}"},
        )

    def resume(self) -> None:
        with self._lock:
            if self._state != "paused":
                return
            self._state = "running"
            self._stop_event.clear()

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        log.info(
            f"timer {self._id} resumed",
            extra={"context": "resume", "state": f"remaining={self._remaining}"},
        )

    def toggle_pause(self) -> None:
        if self.state == "running":
            self.pause()
        elif self.state == "paused":
            self.resume()

    def stop(self) -> None:
        with self._lock:
            self._state = "idle"
            self._stop_event.set()
            self._remaining = self._duration
            self._trigger_fired = False
        log.info(
            f"timer {self._id} stopped",
            extra={"context": "stop", "state": "idle"},
        )

    def reset(self) -> None:
        self.stop()
        self.start()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            time.sleep(1)
            with self._lock:
                if self._state != "running":
                    return
                self._remaining -= 1
                remaining = self._remaining
                trigger_secs = self._trigger_seconds
                trigger_action = self._trigger_action
                trigger_fired = self._trigger_fired

            if self._on_tick:
                self._on_tick(self._id, remaining)

            if (
                trigger_secs is not None
                and trigger_action is not None
                and not trigger_fired
                and remaining <= trigger_secs
            ):
                with self._lock:
                    self._trigger_fired = True
                if self._on_trigger:
                    self._on_trigger(self._id, trigger_action)
                log.info(
                    f"timer {self._id} trigger fired: {trigger_action}",
                    extra={
                        "context": f"trigger at {trigger_secs}s",
                        "state": f"remaining={remaining}",
                    },
                )

            if remaining <= 0:
                with self._lock:
                    self._state = "finished"
                if self._on_finish:
                    self._on_finish(self._id)
                log.info(
                    f"timer {self._id} finished",
                    extra={"context": "countdown complete", "state": "finished"},
                )
                return
