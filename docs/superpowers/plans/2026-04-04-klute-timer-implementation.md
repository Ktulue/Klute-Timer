# Klute-Timer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python desktop stream timer app with Streamer.bot WebSocket integration and OBS text file output, targeting the Bicycle tier.

**Architecture:** Layered Python modules (timer, ws_client, file_writer, config, logger) with a pywebview GUI rendering an HTML/CSS/JS frontend. Streamer.bot WebSocket for bidirectional communication. Each module has one responsibility and communicates through the app bridge.

**Tech Stack:** Python 3.10+, pywebview, websockets, pystray, HTML/CSS/JS

**Spec:** `docs/superpowers/specs/2026-04-04-klute-timer-design.md`

---

## File Structure

```
klute-timer/
├── src/
│   ├── __init__.py
│   ├── app.py              # Entry point, pywebview setup, JS bridge API
│   ├── timer.py            # Timer class with countdown logic and state machine
│   ├── ws_client.py        # Streamer.bot WebSocket client (connect, subscribe, send)
│   ├── file_writer.py      # Atomic text file output for OBS
│   ├── config.py           # JSON config load/save with defaults
│   └── logger.py           # Rotating file logger with pipeline context
├── frontend/
│   ├── index.html          # Main UI layout (4 timer cards + status bar)
│   ├── css/
│   │   └── style.css       # Dark aquatic theme
│   └── js/
│       └── app.js          # Frontend logic, pywebview bridge calls
├── tests/
│   ├── __init__.py
│   ├── test_logger.py
│   ├── test_config.py
│   ├── test_timer.py
│   ├── test_file_writer.py
│   └── test_ws_client.py
├── output/                 # Default text file output (created at runtime)
├── logs/                   # Log files (created at runtime)
├── requirements.txt        # pywebview, websockets, pystray, Pillow
├── requirements-dev.txt    # pytest
├── README.md
└── LICENSE
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `src/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create requirements.txt**

```
pywebview>=5.0
websockets>=12.0
pystray>=0.19
Pillow>=10.0
```

- [ ] **Step 2: Create requirements-dev.txt**

```
-r requirements.txt
pytest>=8.0
```

- [ ] **Step 3: Create package init files**

Create empty `src/__init__.py` and `tests/__init__.py`.

- [ ] **Step 4: Create frontend directory structure**

Create directories: `frontend/css/` and `frontend/js/`.

- [ ] **Step 5: Install dependencies**

Run: `pip install -r requirements-dev.txt`

- [ ] **Step 6: Verify pytest runs**

Run: `pytest --co -q`
Expected: "no tests ran" (no errors)

- [ ] **Step 7: Commit**

```bash
git add requirements.txt requirements-dev.txt src/__init__.py tests/__init__.py
git commit -m "chore: project scaffolding with dependencies"
```

---

### Task 2: Logger Module

**Files:**
- Create: `src/logger.py`
- Create: `tests/test_logger.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_logger.py
import os
import logging
from src.logger import setup_logger, get_logger


class TestLoggerSetup:
    def test_creates_log_directory(self, tmp_path):
        log_dir = tmp_path / "logs"
        setup_logger(log_dir=str(log_dir))
        assert log_dir.exists()

    def test_creates_log_file(self, tmp_path):
        log_dir = tmp_path / "logs"
        setup_logger(log_dir=str(log_dir))
        logger = get_logger("test")
        logger.info("test message")
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) == 1

    def test_log_entry_format(self, tmp_path):
        log_dir = tmp_path / "logs"
        setup_logger(log_dir=str(log_dir))
        logger = get_logger("ws_client")
        logger.error(
            "timer index 5 out of range",
            extra={
                "context": "processing inbound command",
                "state": "ws=connected, timers=[idle]",
            },
        )
        log_file = list(log_dir.glob("*.log"))[0]
        content = log_file.read_text()
        assert "ERROR" in content
        assert "ws_client" in content
        assert "timer index 5 out of range" in content
        assert "processing inbound command" in content
        assert "ws=connected" in content

    def test_default_extra_fields(self, tmp_path):
        log_dir = tmp_path / "logs"
        setup_logger(log_dir=str(log_dir))
        logger = get_logger("timer")
        logger.info("timer started")
        log_file = list(log_dir.glob("*.log"))[0]
        content = log_file.read_text()
        assert "timer" in content
        assert "timer started" in content


class TestLoggerRetrieval:
    def test_get_logger_returns_child(self, tmp_path):
        log_dir = tmp_path / "logs"
        setup_logger(log_dir=str(log_dir))
        logger = get_logger("file_writer")
        assert logger.name == "klute_timer.file_writer"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_logger.py -v`
Expected: FAIL with "ModuleNotFoundError" or "ImportError"

- [ ] **Step 3: Implement logger.py**

```python
# src/logger.py
import os
import logging
from logging.handlers import RotatingFileHandler

_LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | %(name)s"
    " | context: %(context)s | %(message)s | state: %(state)s"
)
_LOG_FORMAT_SIMPLE = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

_ROOT_LOGGER_NAME = "klute_timer"
_initialized = False


class _ContextFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "context"):
            record.context = "none"
        if not hasattr(record, "state"):
            record.state = "none"
        return True


def setup_logger(
    log_dir: str = "logs",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 3,
    level: int = logging.DEBUG,
) -> None:
    global _initialized
    if _initialized:
        return

    os.makedirs(log_dir, exist_ok=True)

    root_logger = logging.getLogger(_ROOT_LOGGER_NAME)
    root_logger.setLevel(level)

    context_filter = _ContextFilter()

    log_path = os.path.join(log_dir, "klute-timer.log")
    file_handler = RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S"))
    file_handler.addFilter(context_filter)

    root_logger.addHandler(file_handler)
    _initialized = True


def get_logger(module_name: str) -> logging.Logger:
    return logging.getLogger(f"{_ROOT_LOGGER_NAME}.{module_name}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_logger.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/logger.py tests/test_logger.py
git commit -m "feat: add rotating file logger with pipeline context"
```

---

### Task 3: Config Module

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: Implement config.py**

```python
# src/config.py
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class PresetConfig:
    name: str
    duration: int
    end_message: str = ""
    trigger_seconds: Optional[int] = None
    trigger_action: Optional[str] = None
    output_file: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


DEFAULT_PRESETS = [
    PresetConfig(
        name="Socials",
        duration=120,
        end_message="",
        trigger_seconds=30,
        trigger_action="Push The Button Reminder",
        output_file="output/socials.txt",
    ),
    PresetConfig(
        name="Intro",
        duration=300,
        end_message="",
        trigger_seconds=None,
        trigger_action=None,
        output_file="output/intro.txt",
    ),
    PresetConfig(
        name="Break",
        duration=600,
        end_message="",
        trigger_seconds=None,
        trigger_action=None,
        output_file="output/break.txt",
    ),
    PresetConfig(
        name="Custom",
        duration=0,
        end_message="",
        trigger_seconds=None,
        trigger_action=None,
        output_file="output/custom.txt",
    ),
]


class Config:
    def __init__(self, config_path: str = "config.json"):
        self._path = config_path
        self.ws_host: str = "127.0.0.1"
        self.ws_port: int = 8059
        self.ws_auth: Optional[str] = None
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

        self.presets = [
            PresetConfig(**p) for p in data.get("presets", [])
        ]

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add JSON config with preset persistence"
```

---

### Task 4: Timer Class

**Files:**
- Create: `src/timer.py`
- Create: `tests/test_timer.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_timer.py
import time
import threading
from src.timer import Timer


class TestTimerState:
    def test_initial_state_is_idle(self):
        t = Timer(timer_id=0, duration=120)
        assert t.state == "idle"
        assert t.remaining == 120

    def test_start_sets_running(self):
        t = Timer(timer_id=0, duration=120)
        t.start()
        assert t.state == "running"
        t.stop()

    def test_pause_from_running(self):
        t = Timer(timer_id=0, duration=120)
        t.start()
        t.pause()
        assert t.state == "paused"
        t.stop()

    def test_resume_from_paused(self):
        t = Timer(timer_id=0, duration=120)
        t.start()
        t.pause()
        t.resume()
        assert t.state == "running"
        t.stop()

    def test_stop_resets_to_idle(self):
        t = Timer(timer_id=0, duration=120)
        t.start()
        t.stop()
        assert t.state == "idle"
        assert t.remaining == 120

    def test_reset_restarts(self):
        t = Timer(timer_id=0, duration=120)
        t.start()
        time.sleep(1.5)
        t.reset()
        assert t.state == "running"
        assert t.remaining == 120
        t.stop()

    def test_pause_toggle(self):
        t = Timer(timer_id=0, duration=120)
        t.start()
        t.toggle_pause()
        assert t.state == "paused"
        t.toggle_pause()
        assert t.state == "running"
        t.stop()


class TestTimerCountdown:
    def test_countdown_decrements(self):
        ticks = []
        t = Timer(timer_id=0, duration=3, on_tick=lambda tid, rem: ticks.append(rem))
        t.start()
        time.sleep(2.5)
        t.stop()
        assert len(ticks) >= 2
        assert ticks[0] == 2
        assert ticks[1] == 1

    def test_countdown_reaches_zero(self):
        finished = threading.Event()
        t = Timer(
            timer_id=0,
            duration=2,
            on_finish=lambda tid: finished.set(),
        )
        t.start()
        finished.wait(timeout=5)
        assert t.state == "finished"
        assert t.remaining == 0

    def test_pause_stops_counting(self):
        ticks = []
        t = Timer(timer_id=0, duration=10, on_tick=lambda tid, rem: ticks.append(rem))
        t.start()
        time.sleep(1.5)
        t.pause()
        count_at_pause = len(ticks)
        time.sleep(2)
        assert len(ticks) == count_at_pause
        t.stop()


class TestTimerTriggerPoint:
    def test_trigger_fires_at_threshold(self):
        triggered = threading.Event()

        def on_trigger(tid, action):
            triggered.set()

        t = Timer(
            timer_id=0,
            duration=3,
            trigger_seconds=1,
            trigger_action="TestAction",
            on_trigger=on_trigger,
        )
        t.start()
        triggered.wait(timeout=5)
        assert triggered.is_set()
        t.stop()

    def test_trigger_does_not_fire_without_config(self):
        triggered = threading.Event()
        t = Timer(
            timer_id=0,
            duration=2,
            on_trigger=lambda tid, action: triggered.set(),
        )
        t.start()
        time.sleep(3)
        assert not triggered.is_set()


class TestTimerFormat:
    def test_format_under_one_hour(self):
        t = Timer(timer_id=0, duration=125)
        assert t.format_remaining() == "02:05"

    def test_format_one_hour_plus(self):
        t = Timer(timer_id=0, duration=3661)
        assert t.format_remaining() == "01:01:01"

    def test_format_at_zero(self):
        t = Timer(timer_id=0, duration=60)
        t._remaining = 0
        assert t.format_remaining() == "00:00"

    def test_format_stays_hms_when_crossing_hour(self):
        t = Timer(timer_id=0, duration=3600)
        t._remaining = 59
        assert t.format_remaining() == "00:00:59"

    def test_format_exact_hour(self):
        t = Timer(timer_id=0, duration=3600)
        assert t.format_remaining() == "01:00:00"


class TestTimerOverrideDuration:
    def test_start_with_override_duration(self):
        t = Timer(timer_id=0, duration=120)
        t.start(override_duration=60)
        assert t.remaining == 60
        t.stop()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_timer.py -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: Implement timer.py**

```python
# src/timer.py
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
            self._remaining = self._duration if override_duration is not None else self._duration
            if self._state != "paused":
                self._remaining = override_duration if override_duration else self._duration
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_timer.py -v`
Expected: All 14 tests PASS

Note: Timer tests use `time.sleep()` and are timing-sensitive. If any test is flaky, increase the sleep margins by 0.5s.

- [ ] **Step 5: Commit**

```bash
git add src/timer.py tests/test_timer.py
git commit -m "feat: add timer class with countdown, trigger points, adaptive formatting"
```

---

### Task 5: File Writer Module

**Files:**
- Create: `src/file_writer.py`
- Create: `tests/test_file_writer.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_file_writer.py
import os
from src.file_writer import FileWriter


class TestFileWriterOutput:
    def test_write_time(self, tmp_path):
        fw = FileWriter()
        path = str(tmp_path / "timer.txt")
        fw.register(0, path)
        fw.write_time(0, "04:23")
        assert open(path).read() == "04:23"

    def test_write_end_message(self, tmp_path):
        fw = FileWriter()
        path = str(tmp_path / "timer.txt")
        fw.register(0, path)
        fw.write_end_message(0, "TIME'S UP")
        assert open(path).read() == "TIME'S UP"

    def test_clear_file(self, tmp_path):
        fw = FileWriter()
        path = str(tmp_path / "timer.txt")
        fw.register(0, path)
        fw.write_time(0, "04:23")
        fw.clear(0)
        assert open(path).read() == ""

    def test_write_blank_end_message(self, tmp_path):
        fw = FileWriter()
        path = str(tmp_path / "timer.txt")
        fw.register(0, path)
        fw.write_end_message(0, "")
        assert open(path).read() == ""

    def test_creates_output_directory(self, tmp_path):
        fw = FileWriter()
        path = str(tmp_path / "subdir" / "timer.txt")
        fw.register(0, path)
        fw.write_time(0, "01:00")
        assert os.path.exists(path)


class TestFileWriterEnforcement:
    def test_rejects_duplicate_path(self, tmp_path):
        fw = FileWriter()
        path = str(tmp_path / "timer.txt")
        fw.register(0, path)
        try:
            fw.register(1, path)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "already assigned" in str(e)

    def test_allows_same_timer_reregister(self, tmp_path):
        fw = FileWriter()
        path = str(tmp_path / "timer.txt")
        fw.register(0, path)
        fw.register(0, str(tmp_path / "other.txt"))
        fw.write_time(0, "01:00")
        assert open(str(tmp_path / "other.txt")).read() == "01:00"

    def test_unregister_frees_path(self, tmp_path):
        fw = FileWriter()
        path = str(tmp_path / "timer.txt")
        fw.register(0, path)
        fw.unregister(0)
        fw.register(1, path)
        fw.write_time(1, "05:00")
        assert open(path).read() == "05:00"


class TestFileWriterAtomicWrite:
    def test_no_temp_file_left_behind(self, tmp_path):
        fw = FileWriter()
        path = str(tmp_path / "timer.txt")
        fw.register(0, path)
        fw.write_time(0, "04:23")
        files = os.listdir(str(tmp_path))
        assert files == ["timer.txt"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_file_writer.py -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: Implement file_writer.py**

```python
# src/file_writer.py
import os
import tempfile
from typing import Optional

from src.logger import get_logger

log = get_logger("file_writer")


class FileWriter:
    def __init__(self):
        self._paths: dict[int, str] = {}

    def register(self, timer_id: int, file_path: str) -> None:
        normalized = os.path.normpath(os.path.abspath(file_path))

        for tid, existing in self._paths.items():
            if existing == normalized and tid != timer_id:
                raise ValueError(
                    f"Path '{file_path}' already assigned to timer {tid}"
                )

        old_path = self._paths.get(timer_id)
        self._paths[timer_id] = normalized

        os.makedirs(os.path.dirname(normalized), exist_ok=True)

        if old_path and old_path != normalized:
            log.info(
                f"timer {timer_id} output changed: {old_path} -> {normalized}",
                extra={"context": "register", "state": f"paths={list(self._paths.values())}"},
            )

    def unregister(self, timer_id: int) -> None:
        self._paths.pop(timer_id, None)

    def write_time(self, timer_id: int, formatted: str) -> None:
        self._atomic_write(timer_id, formatted)

    def write_end_message(self, timer_id: int, message: str) -> None:
        self._atomic_write(timer_id, message)

    def clear(self, timer_id: int) -> None:
        self._atomic_write(timer_id, "")

    def _atomic_write(self, timer_id: int, content: str) -> None:
        path = self._paths.get(timer_id)
        if path is None:
            log.warning(
                f"write attempted for unregistered timer {timer_id}",
                extra={"context": "atomic_write", "state": "no path"},
            )
            return

        dir_path = os.path.dirname(path)
        try:
            fd, tmp_path = tempfile.mkstemp(dir=dir_path, prefix=".klute_")
            try:
                os.write(fd, content.encode("utf-8"))
            finally:
                os.close(fd)
            os.replace(tmp_path, path)
        except OSError:
            log.error(
                f"failed to write to {path}",
                extra={
                    "context": f"writing timer {timer_id}",
                    "state": f"content_length={len(content)}",
                },
            )
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_file_writer.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/file_writer.py tests/test_file_writer.py
git commit -m "feat: add atomic file writer for OBS text output"
```

---

### Task 6: WebSocket Client Module

**Files:**
- Create: `src/ws_client.py`
- Create: `tests/test_ws_client.py`

- [ ] **Step 1: Write the failing tests**

These tests cover message parsing and command routing without requiring an actual WebSocket server.

```python
# tests/test_ws_client.py
import json
from src.ws_client import StreamerbotClient


class TestMessageParsing:
    def test_parse_start_command(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        msg = {
            "timeStamp": "2026-04-04T18:00:00Z",
            "event": {"source": "General", "type": "Custom"},
            "data": {
                "eventName": "klute-timer",
                "useArgs": True,
                "args": {"command": "start", "timer": "1"},
            },
        }
        result = client.parse_command(msg)
        assert result == {"command": "start", "timer": 1}

    def test_parse_start_with_duration(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        msg = {
            "timeStamp": "2026-04-04T18:00:00Z",
            "event": {"source": "General", "type": "Custom"},
            "data": {
                "eventName": "klute-timer",
                "useArgs": True,
                "args": {"command": "start", "timer": "1", "duration": "120"},
            },
        }
        result = client.parse_command(msg)
        assert result == {"command": "start", "timer": 1, "duration": 120}

    def test_parse_pause_command(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        msg = {
            "timeStamp": "2026-04-04T18:00:00Z",
            "event": {"source": "General", "type": "Custom"},
            "data": {
                "eventName": "klute-timer",
                "useArgs": True,
                "args": {"command": "pause", "timer": "2"},
            },
        }
        result = client.parse_command(msg)
        assert result == {"command": "pause", "timer": 2}

    def test_parse_stop_command(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        msg = {
            "timeStamp": "2026-04-04T18:00:00Z",
            "event": {"source": "General", "type": "Custom"},
            "data": {
                "eventName": "klute-timer",
                "useArgs": True,
                "args": {"command": "stop", "timer": "3"},
            },
        }
        result = client.parse_command(msg)
        assert result == {"command": "stop", "timer": 3}

    def test_ignore_non_custom_event(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        msg = {
            "event": {"source": "Twitch", "type": "Follow"},
            "data": {},
        }
        result = client.parse_command(msg)
        assert result is None

    def test_ignore_unknown_command(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        msg = {
            "event": {"source": "General", "type": "Custom"},
            "data": {
                "eventName": "klute-timer",
                "useArgs": True,
                "args": {"command": "explode", "timer": "1"},
            },
        }
        result = client.parse_command(msg)
        assert result is None

    def test_ignore_missing_args(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        msg = {
            "event": {"source": "General", "type": "Custom"},
            "data": {"eventName": "klute-timer", "useArgs": False, "args": None},
        }
        result = client.parse_command(msg)
        assert result is None


class TestSubscribeMessage:
    def test_build_subscribe(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        msg = client.build_subscribe()
        parsed = json.loads(msg)
        assert parsed["request"] == "Subscribe"
        assert "General" in parsed["events"]
        assert "Custom" in parsed["events"]["General"]


class TestDoActionMessage:
    def test_build_do_action(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        msg = client.build_do_action("Push The Button Reminder")
        parsed = json.loads(msg)
        assert parsed["request"] == "DoAction"
        assert parsed["action"]["name"] == "Push The Button Reminder"


class TestReconnectLogic:
    def test_failure_count_tracks(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        assert client.failure_count == 0
        client.record_failure()
        client.record_failure()
        assert client.failure_count == 2
        assert not client.should_notify()

    def test_notify_after_threshold(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        for _ in range(5):
            client.record_failure()
        assert client.should_notify()

    def test_reset_on_success(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        for _ in range(3):
            client.record_failure()
        client.record_success()
        assert client.failure_count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ws_client.py -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: Implement ws_client.py**

```python
# src/ws_client.py
import asyncio
import json
import uuid
import threading
from typing import Optional, Callable

from src.logger import get_logger

log = get_logger("ws_client")

VALID_COMMANDS = {"start", "pause", "stop"}
NOTIFY_THRESHOLD = 5


class StreamerbotClient:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8059,
        on_command: Optional[Callable[[dict], None]] = None,
        on_status_change: Optional[Callable[[str], None]] = None,
    ):
        self._host = host
        self._port = port
        self._on_command = on_command
        self._on_status_change = on_status_change
        self._failure_count = 0
        self._ws = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def uri(self) -> str:
        return f"ws://{self._host}:{self._port}/"

    def record_failure(self) -> None:
        self._failure_count += 1

    def record_success(self) -> None:
        self._failure_count = 0

    def should_notify(self) -> bool:
        return self._failure_count >= NOTIFY_THRESHOLD

    def build_subscribe(self) -> str:
        return json.dumps({
            "request": "Subscribe",
            "id": str(uuid.uuid4()),
            "events": {"General": ["Custom"]},
        })

    def build_do_action(self, action_name: str) -> str:
        return json.dumps({
            "request": "DoAction",
            "id": str(uuid.uuid4()),
            "action": {"name": action_name},
        })

    def parse_command(self, msg: dict) -> Optional[dict]:
        event = msg.get("event", {})
        if event.get("source") != "General" or event.get("type") != "Custom":
            return None

        data = msg.get("data", {})
        args = data.get("args")
        if not args or not data.get("useArgs", False):
            return None

        command = args.get("command")
        if command not in VALID_COMMANDS:
            log.warning(
                f"unknown command: {command}",
                extra={"context": "parse_command", "state": f"args={args}"},
            )
            return None

        try:
            timer_index = int(args["timer"])
        except (KeyError, ValueError):
            log.warning(
                "missing or invalid timer index",
                extra={"context": "parse_command", "state": f"args={args}"},
            )
            return None

        result = {"command": command, "timer": timer_index}

        if "duration" in args:
            try:
                result["duration"] = int(args["duration"])
            except ValueError:
                pass

        return result

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect_loop())

    async def _connect_loop(self) -> None:
        import websockets

        while self._running:
            try:
                if self._on_status_change:
                    self._on_status_change("connecting")

                async with websockets.connect(self.uri) as ws:
                    self._ws = ws
                    self.record_success()

                    if self._on_status_change:
                        self._on_status_change("connected")

                    log.info(
                        f"connected to {self.uri}",
                        extra={"context": "connect", "state": "connected"},
                    )

                    # Wait for Hello, then subscribe
                    hello = await ws.recv()
                    log.info(
                        "received hello",
                        extra={"context": "handshake", "state": "connected"},
                    )

                    await ws.send(self.build_subscribe())
                    sub_response = await ws.recv()
                    log.info(
                        "subscribed to Custom events",
                        extra={"context": "subscribe", "state": "connected"},
                    )

                    async for message in ws:
                        data = json.loads(message)
                        command = self.parse_command(data)
                        if command and self._on_command:
                            self._on_command(command)

            except Exception as e:
                self._ws = None
                self.record_failure()

                if self._on_status_change:
                    status = "error" if self.should_notify() else "reconnecting"
                    self._on_status_change(status)

                log.error(
                    f"connection failed: {e}",
                    extra={
                        "context": "connect_loop",
                        "state": f"failures={self._failure_count}",
                    },
                )

                if not self._running:
                    return

                # Exponential backoff: 1s, 2s, 4s, 8s, max 30s
                delay = min(2 ** (self._failure_count - 1), 30)
                await asyncio.sleep(delay)

    async def send_do_action(self, action_name: str) -> None:
        if self._ws:
            try:
                await self._ws.send(self.build_do_action(action_name))
                log.info(
                    f"sent DoAction: {action_name}",
                    extra={"context": "send_do_action", "state": "connected"},
                )
            except Exception as e:
                log.error(
                    f"failed to send DoAction: {e}",
                    extra={"context": "send_do_action", "state": f"action={action_name}"},
                )

    def trigger_action(self, action_name: str) -> None:
        if self._loop and self._ws:
            asyncio.run_coroutine_threadsafe(
                self.send_do_action(action_name), self._loop
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ws_client.py -v`
Expected: All 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/ws_client.py tests/test_ws_client.py
git commit -m "feat: add Streamer.bot WebSocket client with command parsing and reconnection"
```

---

### Task 7: App Bridge

**Files:**
- Create: `src/app.py`

This is the integration layer that wires all modules together with pywebview. Testing is done via the integration test in Task 10.

- [ ] **Step 1: Implement app.py**

```python
# src/app.py
import os
import sys
import json
import webview
import threading
from typing import Optional

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

    def on_closing():
        for timer in api._timers:
            timer.stop()
        for i in range(len(api._timers)):
            api._file_writer.clear(i)
        if api._ws_client:
            api._ws_client.stop()
        log.info(
            "app closing",
            extra={"context": "shutdown", "state": "closing"},
        )

    window.events.closing += on_closing

    webview.start(start_backend, (window, api), debug=False)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify module imports work**

Run: `python -c "from src.app import Api; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/app.py
git commit -m "feat: add pywebview app bridge wiring all modules together"
```

---

### Task 8: Frontend -- HTML Layout

**Files:**
- Create: `frontend/index.html`

- [ ] **Step 1: Create index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Klute Timer</title>
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <div class="app">
        <header class="status-bar">
            <div class="app-title">Klute Timer</div>
            <div class="ws-status" id="ws-status">
                <span class="ws-indicator" id="ws-indicator"></span>
                <span class="ws-label" id="ws-label">Disconnected</span>
            </div>
        </header>

        <main class="timer-panel" id="timer-panel">
            <!-- Timer cards rendered by JS -->
        </main>

        <footer class="footer-bar">
            <button class="btn-icon" id="btn-logs" title="View Logs">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M2 2h12v2H2V2zm0 4h12v2H2V6zm0 4h8v2H2v-2z"/>
                </svg>
                Logs
            </button>
        </footer>
    </div>

    <!-- Log Viewer Modal -->
    <div class="modal-overlay" id="log-modal" style="display:none;">
        <div class="modal">
            <div class="modal-header">
                <h2>Log Viewer</h2>
                <div class="log-controls">
                    <select id="log-severity">
                        <option value="ALL">All</option>
                        <option value="ERROR">Errors</option>
                        <option value="WARNING">Warnings</option>
                        <option value="INFO" selected>Info+</option>
                    </select>
                    <button class="btn-secondary" id="btn-refresh-logs">Refresh</button>
                </div>
                <button class="btn-close" id="btn-close-logs">&times;</button>
            </div>
            <div class="log-content" id="log-content">
                <pre></pre>
            </div>
        </div>
    </div>

    <!-- Preset Editor Modal -->
    <div class="modal-overlay" id="edit-modal" style="display:none;">
        <div class="modal modal-sm">
            <div class="modal-header">
                <h2>Edit Preset</h2>
                <button class="btn-close" id="btn-close-edit">&times;</button>
            </div>
            <form id="edit-form">
                <input type="hidden" id="edit-timer-id">
                <div class="form-group">
                    <label for="edit-name">Name</label>
                    <input type="text" id="edit-name" maxlength="20">
                </div>
                <div class="form-group">
                    <label for="edit-duration">Duration (seconds)</label>
                    <input type="number" id="edit-duration" min="1" max="86400">
                </div>
                <div class="form-group">
                    <label for="edit-end-message">End Message</label>
                    <input type="text" id="edit-end-message" maxlength="50" placeholder="Blank when done">
                </div>
                <div class="form-group">
                    <label for="edit-trigger-seconds">Trigger at (seconds remaining)</label>
                    <input type="number" id="edit-trigger-seconds" min="0" placeholder="None">
                </div>
                <div class="form-group">
                    <label for="edit-trigger-action">Streamer.bot Action Name</label>
                    <input type="text" id="edit-trigger-action" placeholder="None">
                </div>
                <div class="form-group">
                    <label for="edit-output-file">Output File</label>
                    <input type="text" id="edit-output-file">
                </div>
                <div class="form-actions">
                    <button type="submit" class="btn-primary">Save</button>
                    <button type="button" class="btn-secondary" id="btn-cancel-edit">Cancel</button>
                </div>
            </form>
        </div>
    </div>

    <script src="js/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/index.html
git commit -m "feat: add main HTML layout with timer cards, log viewer, preset editor"
```

---

### Task 9: Frontend -- CSS Theme

**Files:**
- Create: `frontend/css/style.css`

- [ ] **Step 1: Create style.css**

```css
/* frontend/css/style.css */

/* === Reset & Base === */
*, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

:root {
    --bg-primary: #0d1117;
    --bg-secondary: #161b22;
    --bg-tertiary: #1c2128;
    --border: #30363d;

    --text-primary: #e6edf3;
    --text-secondary: #8b949e;
    --text-muted: #6e7681;

    --teal: #2dd4bf;
    --teal-dim: rgba(45, 212, 191, 0.15);
    --amber: #f59e0b;
    --amber-dim: rgba(245, 158, 11, 0.15);
    --red: #ef4444;
    --red-dim: rgba(239, 68, 68, 0.15);
    --gray: #6e7681;
    --gray-dim: rgba(110, 118, 129, 0.15);

    --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    --font-mono: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace;

    --radius: 8px;
    --radius-sm: 4px;
}

body {
    font-family: var(--font-sans);
    background: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.5;
    overflow: hidden;
    height: 100vh;
    user-select: none;
}

/* === App Layout === */
.app {
    display: flex;
    flex-direction: column;
    height: 100vh;
}

/* === Status Bar === */
.status-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 16px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
    -webkit-app-region: drag;
}

.app-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-secondary);
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

.ws-status {
    display: flex;
    align-items: center;
    gap: 6px;
    -webkit-app-region: no-drag;
}

.ws-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--gray);
}

.ws-indicator.connected { background: var(--teal); }
.ws-indicator.connecting,
.ws-indicator.reconnecting { background: var(--amber); }
.ws-indicator.error { background: var(--red); }

.ws-label {
    font-size: 12px;
    color: var(--text-secondary);
}

/* === Timer Panel === */
.timer-panel {
    flex: 1;
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
    padding: 16px;
    overflow: hidden;
}

/* === Timer Card === */
.timer-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.timer-card.state-running {
    border-color: var(--teal);
    background: linear-gradient(var(--bg-secondary), var(--bg-secondary)),
                linear-gradient(var(--teal-dim), var(--teal-dim));
    background-blend-mode: normal;
}

.timer-card.state-paused {
    border-color: var(--amber);
    background: linear-gradient(var(--bg-secondary), var(--bg-secondary)),
                linear-gradient(var(--amber-dim), var(--amber-dim));
}

.timer-card.state-finished {
    border-color: var(--red);
    background: linear-gradient(var(--bg-secondary), var(--bg-secondary)),
                linear-gradient(var(--red-dim), var(--red-dim));
}

/* Card Header */
.card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.timer-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.timer-state {
    font-size: 11px;
    font-weight: 500;
    padding: 2px 8px;
    border-radius: 10px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.timer-state.idle {
    color: var(--gray);
    background: var(--gray-dim);
}

.timer-state.running {
    color: var(--teal);
    background: var(--teal-dim);
}

.timer-state.paused {
    color: var(--amber);
    background: var(--amber-dim);
}

.timer-state.finished {
    color: var(--red);
    background: var(--red-dim);
}

/* Timer Display */
.timer-display {
    font-family: var(--font-mono);
    font-size: 48px;
    font-weight: 700;
    text-align: center;
    color: var(--text-primary);
    padding: 8px 0;
    line-height: 1;
}

/* Card Controls */
.card-controls {
    display: flex;
    gap: 6px;
}

.btn {
    flex: 1;
    padding: 6px 10px;
    font-size: 12px;
    font-weight: 500;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--bg-tertiary);
    color: var(--text-primary);
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
}

.btn:hover {
    background: var(--bg-secondary);
    border-color: var(--text-muted);
}

.btn:active {
    background: var(--bg-primary);
}

.btn:focus-visible {
    outline: 2px solid var(--teal);
    outline-offset: 1px;
}

.btn-start { color: var(--teal); border-color: var(--teal); }
.btn-start:hover { background: var(--teal-dim); }

.btn-pause { color: var(--amber); border-color: var(--amber); }
.btn-pause:hover { background: var(--amber-dim); }

.btn-stop { color: var(--red); border-color: var(--red); }
.btn-stop:hover { background: var(--red-dim); }

.btn-edit {
    flex: 0;
    padding: 6px 8px;
    color: var(--text-muted);
}
.btn-edit:hover { color: var(--text-secondary); }

/* === Footer Bar === */
.footer-bar {
    display: flex;
    align-items: center;
    padding: 6px 16px;
    background: var(--bg-secondary);
    border-top: 1px solid var(--border);
}

.btn-icon {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    font-size: 12px;
    color: var(--text-muted);
    background: none;
    border: none;
    border-radius: var(--radius-sm);
    cursor: pointer;
}

.btn-icon:hover {
    color: var(--text-secondary);
    background: var(--bg-tertiary);
}

/* === Modals === */
.modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
}

.modal {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    width: 90%;
    max-width: 600px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
}

.modal-sm { max-width: 400px; }

.modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
}

.modal-header h2 {
    font-size: 14px;
    font-weight: 600;
}

.log-controls {
    display: flex;
    gap: 8px;
    align-items: center;
}

.btn-close {
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 20px;
    cursor: pointer;
    padding: 0 4px;
}
.btn-close:hover { color: var(--text-primary); }

.log-content {
    flex: 1;
    overflow-y: auto;
    padding: 12px 16px;
}

.log-content pre {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-secondary);
    white-space: pre-wrap;
    word-break: break-all;
}

/* === Form Styles === */
.form-group {
    padding: 8px 16px;
}

.form-group label {
    display: block;
    font-size: 12px;
    color: var(--text-secondary);
    margin-bottom: 4px;
}

.form-group input,
.form-group select {
    width: 100%;
    padding: 6px 10px;
    font-size: 13px;
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text-primary);
}

.form-group input:focus,
.form-group select:focus {
    outline: none;
    border-color: var(--teal);
}

select {
    padding: 4px 8px;
    font-size: 12px;
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text-primary);
}

.form-actions {
    display: flex;
    gap: 8px;
    padding: 12px 16px;
    border-top: 1px solid var(--border);
}

.btn-primary {
    flex: 1;
    padding: 8px 16px;
    background: var(--teal);
    color: var(--bg-primary);
    border: none;
    border-radius: var(--radius-sm);
    font-weight: 600;
    cursor: pointer;
}
.btn-primary:hover { opacity: 0.9; }

.btn-secondary {
    padding: 8px 16px;
    background: var(--bg-tertiary);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    cursor: pointer;
}
.btn-secondary:hover { border-color: var(--text-muted); }

/* === Keyboard Focus === */
*:focus-visible {
    outline: 2px solid var(--teal);
    outline-offset: 1px;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/css/style.css
git commit -m "feat: add dark aquatic CSS theme"
```

---

### Task 10: Frontend -- JavaScript Logic

**Files:**
- Create: `frontend/js/app.js`

- [ ] **Step 1: Create app.js**

```javascript
// frontend/js/app.js

let timers = [];
let presets = [];

// --- Initialization ---

window.addEventListener('pywebviewready', async () => {
    const state = await pywebview.api.get_state();
    presets = await pywebview.api.get_presets();
    timers = state.timers;

    renderTimerCards();
    updateWsStatus(state.ws_status);
    setupEventListeners();
});

// --- Rendering ---

function renderTimerCards() {
    const panel = document.getElementById('timer-panel');
    panel.innerHTML = '';

    timers.forEach((timer, i) => {
        const card = document.createElement('div');
        card.className = `timer-card state-${timer.state}`;
        card.id = `timer-card-${i}`;
        card.innerHTML = `
            <div class="card-header">
                <span class="timer-name">${escapeHtml(timer.name)}</span>
                <span class="timer-state ${timer.state}">${timer.state}</span>
            </div>
            <div class="timer-display" id="timer-display-${i}">${timer.formatted}</div>
            <div class="card-controls">
                <button class="btn btn-start" data-timer="${i}" data-action="start"
                    ${timer.state === 'running' ? 'disabled' : ''}>Start</button>
                <button class="btn btn-pause" data-timer="${i}" data-action="pause"
                    ${timer.state !== 'running' && timer.state !== 'paused' ? 'disabled' : ''}>
                    ${timer.state === 'paused' ? 'Resume' : 'Pause'}</button>
                <button class="btn btn-stop" data-timer="${i}" data-action="stop"
                    ${timer.state === 'idle' ? 'disabled' : ''}>Stop</button>
                <button class="btn btn-edit" data-timer="${i}" data-action="edit"
                    title="Edit preset">&#9881;</button>
            </div>
        `;
        panel.appendChild(card);
    });
}

function updateTimerCard(timer) {
    const card = document.getElementById(`timer-card-${timer.id}`);
    if (!card) return;

    // Update card class
    card.className = `timer-card state-${timer.state}`;

    // Update state badge
    const stateBadge = card.querySelector('.timer-state');
    stateBadge.className = `timer-state ${timer.state}`;
    stateBadge.textContent = timer.state;

    // Update name
    card.querySelector('.timer-name').textContent = timer.name;

    // Update display
    document.getElementById(`timer-display-${timer.id}`).textContent = timer.formatted;

    // Update buttons
    const startBtn = card.querySelector('[data-action="start"]');
    const pauseBtn = card.querySelector('[data-action="pause"]');
    const stopBtn = card.querySelector('[data-action="stop"]');

    startBtn.disabled = timer.state === 'running';
    pauseBtn.disabled = timer.state !== 'running' && timer.state !== 'paused';
    stopBtn.disabled = timer.state === 'idle';
    pauseBtn.textContent = timer.state === 'paused' ? 'Resume' : 'Pause';

    // Update local state
    timers[timer.id] = timer;
}

function updateWsStatus(status) {
    const indicator = document.getElementById('ws-indicator');
    const label = document.getElementById('ws-label');

    indicator.className = `ws-indicator ${status}`;

    const labels = {
        connected: 'Connected',
        disconnected: 'Disconnected',
        connecting: 'Connecting...',
        reconnecting: 'Reconnecting...',
        error: 'Connection Error',
    };
    label.textContent = labels[status] || status;
}

// --- Event Listeners ---

function setupEventListeners() {
    // Timer controls (event delegation)
    document.getElementById('timer-panel').addEventListener('click', (e) => {
        const btn = e.target.closest('[data-action]');
        if (!btn || btn.disabled) return;

        const timerId = parseInt(btn.dataset.timer);
        const action = btn.dataset.action;

        if (action === 'start') pywebview.api.start_timer(timerId);
        else if (action === 'pause') pywebview.api.pause_timer(timerId);
        else if (action === 'stop') pywebview.api.stop_timer(timerId);
        else if (action === 'edit') openEditModal(timerId);
    });

    // Log viewer
    document.getElementById('btn-logs').addEventListener('click', openLogViewer);
    document.getElementById('btn-close-logs').addEventListener('click', closeLogViewer);
    document.getElementById('btn-refresh-logs').addEventListener('click', refreshLogs);
    document.getElementById('log-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeLogViewer();
    });

    // Edit modal
    document.getElementById('btn-close-edit').addEventListener('click', closeEditModal);
    document.getElementById('btn-cancel-edit').addEventListener('click', closeEditModal);
    document.getElementById('edit-form').addEventListener('submit', savePreset);
    document.getElementById('edit-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeEditModal();
    });

    // Keyboard: Escape closes modals
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeLogViewer();
            closeEditModal();
        }
    });
}

// --- Log Viewer ---

async function openLogViewer() {
    document.getElementById('log-modal').style.display = 'flex';
    await refreshLogs();
}

function closeLogViewer() {
    document.getElementById('log-modal').style.display = 'none';
}

async function refreshLogs() {
    const severity = document.getElementById('log-severity').value;
    const logs = await pywebview.api.get_logs(severity, 100);
    document.querySelector('#log-content pre').textContent = logs.join('');
}

// --- Edit Modal ---

function openEditModal(timerId) {
    const preset = presets[timerId];
    document.getElementById('edit-timer-id').value = timerId;
    document.getElementById('edit-name').value = preset.name;
    document.getElementById('edit-duration').value = preset.duration;
    document.getElementById('edit-end-message').value = preset.end_message || '';
    document.getElementById('edit-trigger-seconds').value = preset.trigger_seconds || '';
    document.getElementById('edit-trigger-action').value = preset.trigger_action || '';
    document.getElementById('edit-output-file').value = preset.output_file;
    document.getElementById('edit-modal').style.display = 'flex';
}

function closeEditModal() {
    document.getElementById('edit-modal').style.display = 'none';
}

async function savePreset(e) {
    e.preventDefault();
    const timerId = parseInt(document.getElementById('edit-timer-id').value);
    const triggerSeconds = document.getElementById('edit-trigger-seconds').value;
    const triggerAction = document.getElementById('edit-trigger-action').value;

    const updates = {
        name: document.getElementById('edit-name').value,
        duration: parseInt(document.getElementById('edit-duration').value),
        end_message: document.getElementById('edit-end-message').value,
        trigger_seconds: triggerSeconds ? parseInt(triggerSeconds) : null,
        trigger_action: triggerAction || null,
        output_file: document.getElementById('edit-output-file').value,
    };

    await pywebview.api.update_preset(timerId, updates);
    presets[timerId] = { ...presets[timerId], ...updates };
    closeEditModal();
}

// --- Python Push Handlers ---

window.onTimerUpdate = function(timerState) {
    updateTimerCard(timerState);
};

window.onWsStatusUpdate = function(status) {
    updateWsStatus(status);
};

// --- Utils ---

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/js/app.js
git commit -m "feat: add frontend JS with timer controls, log viewer, preset editor"
```

---

### Task 11: System Tray Integration

**Files:**
- Modify: `src/app.py`

- [ ] **Step 1: Add system tray to app.py**

Add the following imports and tray functions to `src/app.py`. Insert the tray setup into the `main()` function.

Add to imports at the top of `src/app.py`:

```python
import pystray
from PIL import Image, ImageDraw
```

Add this function after the `start_backend` function:

```python
def create_tray_icon() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([8, 8, 56, 56], fill=(45, 212, 191))
    draw.text((22, 18), "K", fill=(13, 17, 23))
    return img
```

Replace the `main()` function with:

```python
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

    def run_tray():
        tray_icon.run()

    tray_thread = threading.Thread(target=run_tray, daemon=True)
    tray_thread.start()

    webview.start(start_backend, (window, api), debug=False)
```

- [ ] **Step 2: Verify the app launches**

Run: `python -m src.app`
Expected: Window opens with 4 timer cards, system tray icon appears. Close window should minimize to tray.

- [ ] **Step 3: Commit**

```bash
git add src/app.py
git commit -m "feat: add system tray with minimize-to-tray support"
```

---

### Task 12: Integration Smoke Test

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Manual smoke test checklist**

Run the app with `python -m src.app` and verify:

- [ ] Window opens with dark aquatic theme
- [ ] 4 timer cards visible (Socials, Intro, Break, Custom)
- [ ] Each card shows preset name, `00:00` display, state label "idle"
- [ ] Click "Start" on Socials timer -- countdown begins from `02:00`, state shows "Running" with teal accent
- [ ] Click "Pause" -- countdown stops, state shows "Paused" with amber accent
- [ ] Click "Resume" (same button) -- countdown resumes
- [ ] Click "Stop" -- resets to `02:00`, state shows "Idle"
- [ ] Timer counts to zero -- state shows "Finished" with red accent
- [ ] Check `output/socials.txt` -- contains formatted countdown, blank when idle
- [ ] Click gear icon -- edit modal opens with preset values
- [ ] Modify preset name and duration, save -- card updates
- [ ] Click "Logs" -- log viewer modal opens with entries
- [ ] Close window -- minimizes to tray (icon visible)
- [ ] Right-click tray icon -- "Show" restores window, "Quit" exits
- [ ] WebSocket status shows "Disconnected" or "Reconnecting" (expected without Streamer.bot running)

- [ ] **Step 2: Write README.md**

```markdown
# Klute Timer

Stream timer app replacing the defunct Elk Timer. Python desktop GUI with Streamer.bot WebSocket integration and text file output for OBS.

## Features

- 4 configurable timer presets (3 defaults + 1 custom)
- Streamer.bot WebSocket integration for Stream Deck triggering
- Text file output for OBS GDI+ text sources
- Configurable trigger points (fire Streamer.bot actions at N seconds remaining)
- Custom end messages per timer
- Dark aquatic theme matching the streaming ecosystem
- In-app log viewer for debugging
- Minimize to system tray

## Setup

### Requirements

- Python 3.10+
- Streamer.bot with WebSocket server enabled (default port: 8059)

### Install

```bash
pip install -r requirements.txt
```

### Run

```bash
python -m src.app
```

### Streamer.bot Configuration

1. Enable WebSocket server in Streamer.bot (Servers/Clients > WebSocket Server)
2. Note your port (default: 8080, Klute Timer defaults to 8059 -- edit `config.json` to match)
3. Create a Streamer.bot action for each timer command:
   - Add sub-action: **Set Argument** `command` = `start` (or `pause`, `stop`)
   - Add sub-action: **Set Argument** `timer` = `1` (1-4, matching preset position)
   - Add sub-action: **Trigger Custom Event**
4. Wire Stream Deck buttons to those Streamer.bot actions

### OBS Setup

Add a GDI+ Text source in OBS pointing to the output file (e.g., `output/socials.txt`). The file updates every second while a timer is running.

## Configuration

Edit `config.json` to customize:

- WebSocket host/port/auth
- Timer presets (name, duration, end message, trigger points)
- Window behavior (minimize to tray)

## License

MIT

---

## Support

☕ [Buy me a coffee on Ko-fi](http://ko-fi.com/ktulue)

Created by Ktulue | The Water Father 🌊
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add README with setup, Streamer.bot config, and OBS instructions"
```

---

## Dependency Summary

Task execution order and dependencies:

```
Task 1  (scaffolding)     -- no deps
Task 2  (logger)          -- depends on Task 1
Task 3  (config)          -- depends on Task 1
Task 4  (timer)           -- depends on Task 2
Task 5  (file_writer)     -- depends on Task 2
Task 6  (ws_client)       -- depends on Task 2
Task 7  (app bridge)      -- depends on Tasks 2-6
Task 8  (HTML)            -- no deps (can parallel with 2-6)
Task 9  (CSS)             -- no deps (can parallel with 2-6)
Task 10 (JS)              -- depends on Task 7 (needs API shape)
Task 11 (system tray)     -- depends on Task 7
Task 12 (smoke test)      -- depends on all
```

Tasks 2, 3 can run in parallel. Tasks 4, 5, 6 can run in parallel. Tasks 8, 9 can run in parallel with 2-6.
