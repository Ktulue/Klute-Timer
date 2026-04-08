# Timer Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the start-after-pause and duration-zero bugs, add a 5-second `00:00` hold + sound alert when a timer expires, add a native file picker for output paths, lock down the unconfirmed `end_message` feature, and delete the unreachable Reset code paths.

**Architecture:** New `SoundPlayer` module wraps `winsound.PlaySound` with a never-raises contract. The `Timer` state machine grows a new `finishing` state that holds `00:00` for 5 seconds via cancellable `stop_event.wait()`, with a new `on_blank` callback that fires when the hold elapses naturally. App layer wires the sound on `_on_finish` and the file clear on `_on_blank`. Frontend gets a Browse button (via `webview.SAVE_DIALOG`), a disabled End Message field, and Start-button gating on duration > 0.

**Tech Stack:** Python 3.12, pywebview, winsound (stdlib), pytest, vanilla JS/HTML in frontend.

**Spec:** `docs/superpowers/specs/2026-04-07-timer-polish-design.md`

**Branch:** `fix/output-file-lifecycle` (already created, spec already committed)

---

## Files Touched

**Created:**
- `src/sound_player.py` — winsound wrapper module
- `tests/test_sound_player.py` — sound player unit tests
- `sounds/.gitkeep` — empty file to commit the sounds directory
- `.gitignore` — repo gitignore (does not exist yet)

**Modified:**
- `src/timer.py` — finishing state, hold loop, start-after-pause fix, duration validation, callback wrapping, delete reset()
- `src/config.py` — add `finished_sound` to PresetConfig, add `default_finished_sound` to Config
- `src/app.py` — wire SoundPlayer, add `_on_blank` callback, add `pick_output_file` bridge, filter end_message in `update_preset`, delete `reset_timer`
- `frontend/js/app.js` — disable Start when duration <= 0, lock end message field, Browse button + handler
- `frontend/index.html` — Browse button markup, locked end message field markup
- `frontend/css/style.css` — disabled-field styling (small additions)
- `config.json` — add `default_finished_sound`, add `finished_sound: null` per preset
- `tests/test_timer.py` — update `test_countdown_reaches_zero`, delete `test_reset_restarts`, add new tests
- `tests/test_config.py` — tests for new fields
- `README.md` — operational notes section

---

## Task 1: Foundation — sounds directory and .gitignore

**Files:**
- Create: `sounds/.gitkeep`
- Create: `.gitignore`

- [ ] **Step 1: Create sounds directory marker**

```bash
mkdir -p sounds
```

Then create `sounds/.gitkeep` as an empty file (use the Write tool with empty content).

- [ ] **Step 2: Create .gitignore**

Create `.gitignore` at the project root with the following content:

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
.pytest_cache/

# Virtual environments
venv/
.venv/
env/

# Logs and runtime output
logs/
output/

# User-supplied audio (the directory itself is committed via .gitkeep)
sounds/*.wav
sounds/*.WAV
!sounds/.gitkeep

# IDE
.vscode/
.idea/

# OS
Thumbs.db
.DS_Store
```

- [ ] **Step 3: Commit**

```bash
git add sounds/.gitkeep .gitignore
git commit -m "maint: add sounds/ directory and .gitignore"
```

---

## Task 2: SoundPlayer module (TDD)

**Files:**
- Create: `tests/test_sound_player.py`
- Create: `src/sound_player.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sound_player.py`:

```python
import os
from unittest.mock import patch
from src.sound_player import SoundPlayer


class TestSoundPlayerSilentCases:
    def test_play_with_none_path_is_silent(self):
        player = SoundPlayer()
        player.play(None)  # must not raise

    def test_play_with_empty_string_is_silent(self):
        player = SoundPlayer()
        player.play("")  # must not raise

    def test_play_with_whitespace_string_is_silent(self):
        player = SoundPlayer()
        player.play("   ")  # must not raise


class TestSoundPlayerErrorHandling:
    def test_play_with_missing_file_does_not_raise(self, caplog):
        player = SoundPlayer()
        player.play("/nonexistent/path/to/file.wav")  # must not raise
        assert any("not found" in r.message.lower() or "does not exist" in r.message.lower()
                   for r in caplog.records)

    def test_play_with_winsound_exception_does_not_raise(self, tmp_path):
        # Create a real file so the existence check passes
        wav_path = tmp_path / "fake.wav"
        wav_path.write_bytes(b"not a real wav")

        with patch("src.sound_player.winsound.PlaySound") as mock_play:
            mock_play.side_effect = RuntimeError("simulated audio failure")
            player = SoundPlayer()
            player.play(str(wav_path))  # must not raise

    def test_play_never_raises_on_oserror(self, tmp_path):
        wav_path = tmp_path / "fake.wav"
        wav_path.write_bytes(b"not a real wav")

        with patch("src.sound_player.winsound.PlaySound") as mock_play:
            mock_play.side_effect = OSError("device unavailable")
            player = SoundPlayer()
            player.play(str(wav_path))  # must not raise


class TestSoundPlayerSuccess:
    def test_play_with_valid_path_calls_winsound(self, tmp_path):
        wav_path = tmp_path / "test.wav"
        wav_path.write_bytes(b"fake wav bytes")

        with patch("src.sound_player.winsound.PlaySound") as mock_play:
            player = SoundPlayer()
            player.play(str(wav_path))
            mock_play.assert_called_once()
            # Verify SND_ASYNC and SND_FILENAME flags were passed
            call_args = mock_play.call_args
            import winsound
            flags = call_args[0][1]
            assert flags & winsound.SND_ASYNC
            assert flags & winsound.SND_FILENAME
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_sound_player.py -v
```

Expected: ImportError or `ModuleNotFoundError: No module named 'src.sound_player'`

- [ ] **Step 3: Implement SoundPlayer**

Create `src/sound_player.py`:

```python
import os
import winsound
from typing import Optional

from src.logger import get_logger

log = get_logger("sound_player")


class SoundPlayer:
    """Plays WAV files via winsound. Never raises.

    Failure modes (None path, missing file, invalid WAV, OS error) are
    logged and swallowed so the timer's run thread cannot be killed by
    a sound playback issue.
    """

    def play(self, path: Optional[str]) -> None:
        if path is None or not path.strip():
            return

        normalized = os.path.abspath(path)

        if not os.path.exists(normalized):
            log.warning(
                f"sound file not found: {normalized}",
                extra={"context": "play", "state": f"path={path}"},
            )
            return

        try:
            winsound.PlaySound(
                normalized,
                winsound.SND_FILENAME | winsound.SND_ASYNC,
            )
        except Exception as e:
            log.error(
                f"winsound playback failed: {e}",
                extra={"context": "play", "state": f"path={normalized}"},
            )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_sound_player.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/sound_player.py tests/test_sound_player.py
git commit -m "feat: add SoundPlayer module with never-raises contract"
```

---

## Task 3: Config schema — add finished_sound fields (TDD)

**Files:**
- Modify: `src/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_config.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config.py::TestConfigFinishedSound -v
```

Expected: AttributeError: 'PresetConfig' object has no attribute 'finished_sound' (or similar)

- [ ] **Step 3: Modify `src/config.py`**

Update the `PresetConfig` dataclass to add `finished_sound`:

```python
@dataclass
class PresetConfig:
    name: str
    duration: int
    end_message: str = ""
    trigger_seconds: Optional[int] = None
    trigger_action: Optional[str] = None
    output_file: str = ""
    finished_sound: Optional[str] = None
```

Update `Config.__init__` to add `default_finished_sound`:

```python
class Config:
    def __init__(self, config_path: str = "config.json"):
        self._path = config_path
        self.ws_host: str = "127.0.0.1"
        self.ws_port: int = 8059
        self.ws_auth: Optional[str] = None
        self.default_finished_sound: Optional[str] = None
        self.presets: list[PresetConfig] = []
        self.minimize_to_tray: bool = True

        if os.path.exists(self._path):
            self._load()
        else:
            self._set_defaults()
            self.save()
```

Update `_set_defaults`:

```python
    def _set_defaults(self) -> None:
        self.ws_host = "127.0.0.1"
        self.ws_port = 8059
        self.ws_auth = None
        self.default_finished_sound = None
        self.presets = [
            PresetConfig(**asdict(p)) for p in DEFAULT_PRESETS
        ]
        self.minimize_to_tray = True
```

Update `_load`:

```python
    def _load(self) -> None:
        with open(self._path, "r", encoding="utf-8") as f:
            data = json.load(f)

        ws = data.get("websocket", {})
        self.ws_host = ws.get("host", "127.0.0.1")
        self.ws_port = ws.get("port", 8059)
        self.ws_auth = ws.get("auth", None)

        self.default_finished_sound = data.get("default_finished_sound", None)

        self.presets = [
            PresetConfig(**p) for p in data.get("presets", [])
        ]

        window = data.get("window", {})
        self.minimize_to_tray = window.get("minimize_to_tray", True)
```

Update `save`:

```python
    def save(self) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        data = {
            "websocket": {
                "host": self.ws_host,
                "port": self.ws_port,
                "auth": self.ws_auth,
            },
            "default_finished_sound": self.default_finished_sound,
            "presets": [p.to_dict() for p in self.presets],
            "window": {
                "minimize_to_tray": self.minimize_to_tray,
            },
        }
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected: all tests PASS (including the existing tests, since the new field is backward-compatible via defaults)

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add finished_sound and default_finished_sound to config schema"
```

---

## Task 4: Timer — finishing state with cancellable 5-second hold (TDD)

This is the largest task. The Timer gets a new state, a new constructor parameter (`hold_seconds`), a new callback (`on_blank`), and a hold loop. One existing test is updated and one is deleted as a side effect.

**Files:**
- Modify: `src/timer.py`
- Modify: `tests/test_timer.py`

- [ ] **Step 1: Update existing `test_countdown_reaches_zero` and add new tests**

Replace the existing `TestTimerCountdown.test_countdown_reaches_zero` in `tests/test_timer.py` (line 70-80) with:

```python
    def test_countdown_reaches_finishing_then_finished(self):
        finished_callback_fired = threading.Event()
        blank_callback_fired = threading.Event()
        t = Timer(
            timer_id=0,
            duration=2,
            hold_seconds=0.1,
            on_finish=lambda tid: finished_callback_fired.set(),
            on_blank=lambda tid: blank_callback_fired.set(),
        )
        t.start()
        finished_callback_fired.wait(timeout=5)
        # When on_finish fires, state should be 'finishing' (the hold has begun)
        assert t.state == "finishing"
        assert t.remaining == 0
        # Wait for the hold to elapse and on_blank to fire
        blank_callback_fired.wait(timeout=2)
        assert t.state == "finished"
```

Append a new test class to `tests/test_timer.py`:

```python
class TestTimerFinishingState:
    def test_finishing_state_holds_for_hold_seconds(self):
        finish_event = threading.Event()
        blank_event = threading.Event()
        t = Timer(
            timer_id=0,
            duration=1,
            hold_seconds=0.3,
            on_finish=lambda tid: finish_event.set(),
            on_blank=lambda tid: blank_event.set(),
        )
        t.start()
        finish_event.wait(timeout=5)
        # Immediately after on_finish, state must be 'finishing', not 'finished'
        assert t.state == "finishing"
        # on_blank should NOT have fired yet
        assert not blank_event.is_set()
        # Now wait for the hold to elapse
        blank_event.wait(timeout=2)
        assert t.state == "finished"

    def test_finishing_cancelled_by_stop(self):
        finish_event = threading.Event()
        blank_event = threading.Event()
        t = Timer(
            timer_id=0,
            duration=1,
            hold_seconds=2.0,
            on_finish=lambda tid: finish_event.set(),
            on_blank=lambda tid: blank_event.set(),
        )
        t.start()
        finish_event.wait(timeout=5)
        assert t.state == "finishing"
        t.stop()
        assert t.state == "idle"
        # Give the thread a moment to exit
        time.sleep(0.1)
        # on_blank must NOT have fired — Stop interrupts the hold
        assert not blank_event.is_set()

    def test_finishing_cancelled_by_start(self):
        finish_event = threading.Event()
        blank_event = threading.Event()
        t = Timer(
            timer_id=0,
            duration=1,
            hold_seconds=2.0,
            on_finish=lambda tid: finish_event.set(),
            on_blank=lambda tid: blank_event.set(),
        )
        t.start()
        finish_event.wait(timeout=5)
        assert t.state == "finishing"
        t.start()  # interrupt with a new start
        time.sleep(0.05)
        assert t.state == "running"
        assert t.remaining > 0
        assert not blank_event.is_set()
        t.stop()

    def test_pause_during_finishing_is_noop(self):
        finish_event = threading.Event()
        t = Timer(
            timer_id=0,
            duration=1,
            hold_seconds=1.0,
            on_finish=lambda tid: finish_event.set(),
        )
        t.start()
        finish_event.wait(timeout=5)
        assert t.state == "finishing"
        t.pause()
        # Pause should NOT change the state during finishing
        assert t.state == "finishing"
        t.stop()

    def test_on_finish_callback_exception_does_not_crash_thread(self):
        blank_event = threading.Event()

        def raising_on_finish(tid):
            raise RuntimeError("simulated callback failure")

        t = Timer(
            timer_id=0,
            duration=1,
            hold_seconds=0.2,
            on_finish=raising_on_finish,
            on_blank=lambda tid: blank_event.set(),
        )
        t.start()
        # Even though on_finish raised, the hold should still proceed and on_blank should fire
        blank_event.wait(timeout=3)
        assert blank_event.is_set()
        assert t.state == "finished"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_timer.py::TestTimerFinishingState tests/test_timer.py::TestTimerCountdown::test_countdown_reaches_finishing_then_finished -v
```

Expected: TypeErrors about unknown `hold_seconds` and `on_blank` constructor arguments.

- [ ] **Step 3: Modify `src/timer.py`**

Update the `Timer` class. Replace the entire file with:

```python
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
        on_blank: Optional[Callable[[int], None]] = None,
        hold_seconds: float = 5.0,
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
        self._on_blank = on_blank
        self._hold_seconds = hold_seconds
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

            # Resume from paused: do not reset _remaining
            if self._state == "paused":
                self._state = "running"
                self._stop_event.clear()
                self._thread = threading.Thread(target=self._run, daemon=True)
                self._thread.start()
                log.info(
                    f"timer {self._id} resumed via start ({self._remaining}s remaining)",
                    extra={"context": "start", "state": f"remaining={self._remaining}"},
                )
                return

            # Fresh start (from idle, finishing, or finished): reset _remaining
            effective_duration = override_duration if override_duration is not None else self._duration
            if effective_duration <= 0:
                log.warning(
                    f"timer {self._id} start rejected: duration must be > 0 (got {effective_duration})",
                    extra={"context": "start", "state": f"duration={effective_duration}"},
                )
                return

            if override_duration is not None:
                self._duration = override_duration
                self._use_hms = override_duration >= 3600

            self._remaining = self._duration
            self._trigger_fired = False
            self._state = "running"
            self._stop_event.set()  # Wake up any in-progress hold wait
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

    def _safe_call(self, callback, *args) -> None:
        """Invoke a callback without letting exceptions escape into the run thread."""
        if callback is None:
            return
        try:
            callback(*args)
        except Exception as e:
            log.error(
                f"timer {self._id} callback raised: {e}",
                extra={"context": "callback", "state": f"callback={callback.__name__ if hasattr(callback, '__name__') else 'lambda'}"},
            )

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

            self._safe_call(self._on_tick, self._id, remaining)

            if (
                trigger_secs is not None
                and trigger_action is not None
                and not trigger_fired
                and remaining <= trigger_secs
            ):
                with self._lock:
                    self._trigger_fired = True
                self._safe_call(self._on_trigger, self._id, trigger_action)
                log.info(
                    f"timer {self._id} trigger fired: {trigger_action}",
                    extra={
                        "context": f"trigger at {trigger_secs}s",
                        "state": f"remaining={remaining}",
                    },
                )

            if remaining <= 0:
                with self._lock:
                    self._state = "finishing"
                self._safe_call(self._on_finish, self._id)
                log.info(
                    f"timer {self._id} entering finishing state ({self._hold_seconds}s hold)",
                    extra={"context": "countdown complete", "state": "finishing"},
                )

                # Cancellable hold: wait() returns True if the event was set
                # (cancelled by stop/start), False if the timeout elapsed naturally.
                cancelled = self._stop_event.wait(self._hold_seconds)
                if cancelled:
                    # Some other handler (stop/start) is managing state and file.
                    log.info(
                        f"timer {self._id} hold cancelled",
                        extra={"context": "hold cancelled", "state": self.state},
                    )
                    return

                with self._lock:
                    # Only transition to finished if no one else changed state during the hold
                    if self._state == "finishing":
                        self._state = "finished"
                self._safe_call(self._on_blank, self._id)
                log.info(
                    f"timer {self._id} hold elapsed, blanking",
                    extra={"context": "hold complete", "state": "finished"},
                )
                return
```

**Note about the `start()` rewrite:** When transitioning from any state other than `paused`/`running` and a previous run thread is still in its hold loop (`finishing` state), we set then immediately clear the `_stop_event`. The set wakes up the in-progress `wait()`, which returns `True` (cancelled) and the old thread exits cleanly. The clear then lets the new thread's run loop proceed without immediately exiting. This is the cleanest way to interrupt a hold from a fresh start.

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_timer.py -v
```

Expected: All `TestTimerFinishingState` tests pass, the updated `test_countdown_reaches_finishing_then_finished` passes, and all unrelated existing tests (initial state, pause/resume, format, trigger point) still pass.

If `test_reset_restarts` (line 40-47 of the original file) fails because it calls `t.reset()` — leave it failing for now. Task 7 deletes `Timer.reset()` and that test together.

- [ ] **Step 5: Commit**

```bash
git add src/timer.py tests/test_timer.py
git commit -m "feat: add Timer finishing state with cancellable 5-second hold"
```

---

## Task 5: Timer — fix start-after-pause bug (TDD)

The fix already landed in Task 4 (the rewritten `start()` method handles the paused branch). This task adds an explicit regression test so the bug can never quietly come back.

**Files:**
- Modify: `tests/test_timer.py`

- [ ] **Step 1: Add the regression test**

Append a new test class to `tests/test_timer.py`:

```python
class TestTimerStartAfterPause:
    def test_start_after_pause_resumes_does_not_restart(self):
        """Regression test for bug found in first build:
        Pressing Start while paused must resume from current remaining,
        not reset to full duration."""
        t = Timer(timer_id=0, duration=10)
        t.start()
        time.sleep(2.5)
        t.pause()
        remaining_at_pause = t.remaining
        # remaining should be ~7 or 8 (started at 10, ran for ~2.5s)
        assert remaining_at_pause < 10
        assert remaining_at_pause >= 6  # tolerate timing variance

        t.start()  # Press Start while paused — should resume, not restart
        assert t.state == "running"
        # remaining should still be close to remaining_at_pause, NOT reset to 10
        assert t.remaining <= remaining_at_pause
        assert t.remaining >= remaining_at_pause - 1  # might tick once during the assertion
        t.stop()
```

- [ ] **Step 2: Run the test to verify it passes**

```bash
pytest tests/test_timer.py::TestTimerStartAfterPause -v
```

Expected: PASS (the fix is already in `start()` from Task 4)

- [ ] **Step 3: Commit**

```bash
git add tests/test_timer.py
git commit -m "test: add regression test for start-after-pause resume behavior"
```

---

## Task 6: Timer — duration validation + callback exception wrapping (TDD)

The implementations already landed in Task 4 (the duration check in `start()` and the `_safe_call` helper). This task adds explicit regression tests for both behaviors.

**Files:**
- Modify: `tests/test_timer.py`

- [ ] **Step 1: Add the regression tests**

Append a new test class to `tests/test_timer.py`:

```python
class TestTimerDurationValidation:
    def test_start_with_zero_duration_is_rejected(self, caplog):
        t = Timer(timer_id=0, duration=0)
        t.start()
        assert t.state == "idle"
        assert t.remaining == 0
        assert any("rejected" in r.message.lower() for r in caplog.records)

    def test_start_with_negative_duration_is_rejected(self, caplog):
        t = Timer(timer_id=0, duration=-5)
        t.start()
        assert t.state == "idle"
        assert any("rejected" in r.message.lower() for r in caplog.records)

    def test_start_with_zero_override_duration_is_rejected(self):
        t = Timer(timer_id=0, duration=60)
        t.start(override_duration=0)
        assert t.state == "idle"


class TestTimerCallbackSafety:
    def test_on_tick_exception_does_not_crash_thread(self):
        ticks_after_exception = []

        def raising_then_recording_tick(tid, rem):
            if not ticks_after_exception:
                ticks_after_exception.append(rem)
                raise RuntimeError("first tick fails")
            ticks_after_exception.append(rem)

        t = Timer(timer_id=0, duration=4, on_tick=raising_then_recording_tick)
        t.start()
        time.sleep(2.5)
        # The first tick raised but the thread should still have ticked again
        assert len(ticks_after_exception) >= 2
        t.stop()

    def test_on_trigger_exception_does_not_crash_thread(self):
        ticks = []

        def raising_trigger(tid, action):
            raise RuntimeError("trigger fails")

        t = Timer(
            timer_id=0,
            duration=3,
            trigger_seconds=2,
            trigger_action="x",
            on_trigger=raising_trigger,
            on_tick=lambda tid, rem: ticks.append(rem),
        )
        t.start()
        time.sleep(2.5)
        # Trigger should have fired and raised, but countdown continues
        assert len(ticks) >= 2
        t.stop()
```

- [ ] **Step 2: Run the tests to verify they pass**

```bash
pytest tests/test_timer.py::TestTimerDurationValidation tests/test_timer.py::TestTimerCallbackSafety -v
```

Expected: PASS (both behaviors implemented in Task 4)

- [ ] **Step 3: Commit**

```bash
git add tests/test_timer.py
git commit -m "test: add regression tests for duration validation and callback safety"
```

---

## Task 7: Timer — delete reset method and its test

**Files:**
- Modify: `src/timer.py`
- Modify: `tests/test_timer.py`

- [ ] **Step 1: Delete `test_reset_restarts` from `tests/test_timer.py`**

Find and delete the existing `test_reset_restarts` method (line 40-47 in the original file, in `class TestTimerState`):

```python
    def test_reset_restarts(self):
        t = Timer(timer_id=0, duration=120)
        t.start()
        time.sleep(1.5)
        t.reset()
        assert t.state == "running"
        assert t.remaining == 120
        t.stop()
```

Delete the entire method (8 lines).

- [ ] **Step 2: Add a defensive test that asserts the method is gone**

Append to the `TestTimerState` class in `tests/test_timer.py`:

```python
    def test_reset_method_does_not_exist(self):
        """Defensive guard: Timer.reset() was deleted as part of the timer
        polish work because there was no UI affordance for it. Stop already
        does halt+reset+clear in one verb. If reset() comes back, it should
        come back via a deliberate spec, not by accident."""
        t = Timer(timer_id=0, duration=120)
        assert not hasattr(t, "reset")
```

- [ ] **Step 3: Delete `Timer.reset` from `src/timer.py`**

Delete the `reset` method from `src/timer.py` (lines 128-130 in the original file):

```python
    def reset(self) -> None:
        self.stop()
        self.start()
```

- [ ] **Step 4: Run the tests to verify both the delete and the defensive test work**

```bash
pytest tests/test_timer.py -v
```

Expected: All tests PASS, including the new `test_reset_method_does_not_exist`. The deleted `test_reset_restarts` is no longer collected.

- [ ] **Step 5: Commit**

```bash
git add src/timer.py tests/test_timer.py
git commit -m "maint: delete Timer.reset() and its test (no UI affordance, stop covers it)"
```

---

## Task 8: app.py — wire SoundPlayer, on_blank handler, drop end_message write

**Files:**
- Modify: `src/app.py`

- [ ] **Step 1: Add SoundPlayer import and instantiation**

In `src/app.py`, add this import near the top with the other `src.` imports:

```python
from src.sound_player import SoundPlayer
```

In `Api.__init__`, add the SoundPlayer instance after the file_writer:

```python
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
```

- [ ] **Step 2: Pass `on_blank` callback when constructing timers**

In `_init_timers`, add `on_blank=self._on_blank` to the Timer constructor:

```python
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
```

- [ ] **Step 3: Replace `_on_finish` to play sound instead of writing end_message**

Replace the existing `_on_finish` method with:

```python
    def _on_finish(self, timer_id: int) -> None:
        preset = self._config.presets[timer_id]
        sound = preset.finished_sound or self._config.default_finished_sound
        self._sound_player.play(sound)
        self._push_timer_update(timer_id)
```

- [ ] **Step 4: Add `_on_blank` method**

Add the new `_on_blank` method after `_on_finish`:

```python
    def _on_blank(self, timer_id: int) -> None:
        self._file_writer.clear(timer_id)
        self._push_timer_update(timer_id)
```

- [ ] **Step 5: Manual smoke test**

Run the app via `launch.bat` and verify:
1. Set the Custom preset's duration to 5 in the GUI
2. Click Start
3. Watch the output file (`output/custom.txt`) in VS Code or `Get-Content -Wait`
4. When the countdown hits 0, you should hear the chimes (after Task 14 sets the default in config.json — until then, no sound, but no crash)
5. The file should show `00:00` for 5 seconds, then blank

**Note:** Until Task 14 lands, `default_finished_sound` is `None` so no sound plays — that's expected. The visible 5-second hold + auto-blank is the verification target for this task.

- [ ] **Step 6: Commit**

```bash
git add src/app.py
git commit -m "feat: wire SoundPlayer and on_blank callback into app, drop end_message write"
```

---

## Task 9: app.py — filter end_message in update_preset (TDD)

**Files:**
- Modify: `src/app.py`
- Create: `tests/test_app_update_preset.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_app_update_preset.py`:

```python
import os
from unittest.mock import MagicMock, patch
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
        import json
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
        assert any("end_message" in r.message and ("paused" in r.message.lower() or "ignor" in r.message.lower())
                   for r in caplog.records)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/test_app_update_preset.py -v
```

Expected: assertion failure on `end_message == "original"` (currently `update_preset` accepts the change).

- [ ] **Step 3: Modify `update_preset` in `src/app.py`**

Replace the existing `update_preset` method with:

```python
    def update_preset(self, timer_id: int, updates: dict) -> None:
        if not (0 <= timer_id < len(self._config.presets)):
            return

        # end_message feature is paused — silently drop any attempted updates
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
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/test_app_update_preset.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/app.py tests/test_app_update_preset.py
git commit -m "feat: filter end_message updates in update_preset (feature paused)"
```

---

## Task 10: app.py — pick_output_file bridge method

**Files:**
- Modify: `src/app.py`

- [ ] **Step 1: Add the `pick_output_file` method**

Add this method to the `Api` class in `src/app.py`, near the other JS bridge methods (after `update_preset`):

```python
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
```

**Note:** The pywebview file dialog cannot be reasonably unit-tested (it's a native OS dialog). This task has no unit test for the dialog interaction itself — it's covered by manual smoke tests #9-12 in the spec. The validation logic is pure functions and could be extracted into a helper for unit testing, but for now we accept the manual coverage.

- [ ] **Step 2: Manual smoke test**

This will be exercised end-to-end after Task 13 (Browse button) lands. For now, verify the method imports and exists:

```bash
python -c "from src.app import Api; assert hasattr(Api, 'pick_output_file'); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/app.py
git commit -m "feat: add pick_output_file bridge method with native save dialog"
```

---

## Task 11: app.py — delete reset_timer

**Files:**
- Modify: `src/app.py`

- [ ] **Step 1: Delete the `reset_timer` method**

Find and delete the existing `reset_timer` method in `src/app.py` (lines 161-164 in the original file):

```python
    def reset_timer(self, timer_id: int) -> None:
        if 0 <= timer_id < len(self._timers):
            self._timers[timer_id].reset()
            self._push_timer_update(timer_id)
```

- [ ] **Step 2: Verify there are no remaining references**

```bash
grep -rn "reset_timer\|api\.reset" src/ frontend/ tests/
```

Expected: no matches (or only the deletion you just made; if anything in `frontend/` references `reset_timer`, you'll need to remove it too — though there should be nothing since there's no Reset button).

- [ ] **Step 3: Smoke-import test**

```bash
python -c "from src.app import Api; assert not hasattr(Api, 'reset_timer'); print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/app.py
git commit -m "maint: delete Api.reset_timer (no UI affordance, dead code)"
```

---

## Task 12: Frontend — disable Start button when duration <= 0

**Files:**
- Modify: `frontend/js/app.js`

- [ ] **Step 1: Update `renderTimerCards` to disable Start when duration is invalid**

In `frontend/js/app.js`, find the `renderTimerCards` function (around line 20). Replace the Start button line in the template with one that also checks duration:

Find this block:

```javascript
                <button class="btn btn-start" data-timer="${i}" data-action="start"
                    ${timer.state === 'running' ? 'disabled' : ''}>Start</button>
```

Replace with:

```javascript
                <button class="btn btn-start" data-timer="${i}" data-action="start"
                    ${timer.state === 'running' || (presets[i] && presets[i].duration <= 0) ? 'disabled' : ''}
                    ${presets[i] && presets[i].duration <= 0 ? 'title="Set a duration > 0 to start"' : ''}>Start</button>
```

- [ ] **Step 2: Update `updateTimerCard` to apply the same gating on state pushes**

In `updateTimerCard` (around line 50), find the line:

```javascript
    startBtn.disabled = timer.state === 'running';
```

Replace with:

```javascript
    const preset = presets[timer.id];
    startBtn.disabled = timer.state === 'running' || (preset && preset.duration <= 0);
    if (preset && preset.duration <= 0) {
        startBtn.title = 'Set a duration > 0 to start';
    } else {
        startBtn.removeAttribute('title');
    }
```

- [ ] **Step 3: Update `savePreset` to refresh the rendered cards after a duration change**

In `savePreset` (around line 175), after updating the local `presets` array, add a re-render call. Find this block:

```javascript
    await pywebview.api.update_preset(timerId, updates);
    presets[timerId] = { ...presets[timerId], ...updates };
    closeEditModal();
```

Replace with:

```javascript
    await pywebview.api.update_preset(timerId, updates);
    presets[timerId] = { ...presets[timerId], ...updates };
    // Re-render so the Start button reflects the new duration
    const updatedState = await pywebview.api.get_state();
    timers = updatedState.timers;
    renderTimerCards();
    closeEditModal();
```

- [ ] **Step 4: Manual smoke test**

```bash
launch.bat
```

In the GUI:
1. Open the Custom preset editor (the gear icon)
2. Confirm Custom's Start button is disabled (Custom has duration=0 by default)
3. Edit Custom, set duration to 10, Save
4. Confirm Start button is now enabled
5. Edit Custom, set duration to 0, Save
6. Confirm Start button is disabled again

- [ ] **Step 5: Commit**

```bash
git add frontend/js/app.js
git commit -m "feat: disable Start button when preset duration <= 0"
```

---

## Task 13: Frontend — lock end_message field in preset editor

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/js/app.js`
- Modify: `frontend/css/style.css`

- [ ] **Step 1: Update the End Message form group in `frontend/index.html`**

Find this block (around line 72-75):

```html
                <div class="form-group">
                    <label for="edit-end-message">End Message</label>
                    <input type="text" id="edit-end-message" maxlength="50" placeholder="Blank when done">
                </div>
```

Replace with:

```html
                <div class="form-group form-group-locked">
                    <label for="edit-end-message">End Message</label>
                    <input type="text" id="edit-end-message" maxlength="50" disabled>
                    <small class="form-helper">Paused — returning in a future update</small>
                </div>
```

- [ ] **Step 2: Update `savePreset` in `frontend/js/app.js` to NOT send end_message**

Find this block in `savePreset`:

```javascript
    const updates = {
        name: document.getElementById('edit-name').value,
        duration: parseInt(document.getElementById('edit-duration').value),
        end_message: document.getElementById('edit-end-message').value,
        trigger_seconds: triggerSeconds ? parseInt(triggerSeconds) : null,
        trigger_action: triggerAction || null,
        output_file: document.getElementById('edit-output-file').value,
    };
```

Replace with (drop the `end_message` line entirely):

```javascript
    const updates = {
        name: document.getElementById('edit-name').value,
        duration: parseInt(document.getElementById('edit-duration').value),
        trigger_seconds: triggerSeconds ? parseInt(triggerSeconds) : null,
        trigger_action: triggerAction || null,
        output_file: document.getElementById('edit-output-file').value,
    };
```

- [ ] **Step 3: Add disabled-field styling to `frontend/css/style.css`**

Append to `frontend/css/style.css`:

```css
/* Locked form fields (e.g. paused features) */
.form-group-locked input[disabled] {
    opacity: 0.5;
    cursor: not-allowed;
    background: rgba(255, 255, 255, 0.04);
}

.form-helper {
    display: block;
    margin-top: 4px;
    font-size: 0.8em;
    color: #6b7d8a;
    font-style: italic;
}
```

- [ ] **Step 4: Manual smoke test**

```bash
launch.bat
```

1. Open any preset's editor (gear icon)
2. Confirm the End Message field is greyed out and not editable
3. Confirm the helper text reads "Paused — returning in a future update"
4. Try to save the preset — confirm it saves without error
5. Reopen the editor — confirm other fields persisted

- [ ] **Step 5: Commit**

```bash
git add frontend/index.html frontend/js/app.js frontend/css/style.css
git commit -m "feat: lock end_message field in preset editor (feature paused)"
```

---

## Task 14: Frontend — Browse button for output file

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/js/app.js`
- Modify: `frontend/css/style.css`

- [ ] **Step 1: Update the Output File form group in `frontend/index.html`**

Find this block (around line 84-87):

```html
                <div class="form-group">
                    <label for="edit-output-file">Output File</label>
                    <input type="text" id="edit-output-file">
                </div>
```

Replace with:

```html
                <div class="form-group">
                    <label for="edit-output-file">Output File</label>
                    <div class="input-with-button">
                        <input type="text" id="edit-output-file" readonly>
                        <button type="button" class="btn-secondary" id="btn-browse-output">Browse...</button>
                    </div>
                    <small class="form-helper" id="output-file-error" style="display:none; color:#ff6b6b;"></small>
                </div>
```

- [ ] **Step 2: Add the Browse handler in `frontend/js/app.js`**

In `setupEventListeners` (around line 100), after the existing edit modal listeners, add:

```javascript
    // Browse button for output file
    document.getElementById('btn-browse-output').addEventListener('click', async () => {
        const timerId = parseInt(document.getElementById('edit-timer-id').value);
        const errorEl = document.getElementById('output-file-error');
        errorEl.style.display = 'none';

        const result = await pywebview.api.pick_output_file(timerId);
        if (result) {
            document.getElementById('edit-output-file').value = result;
            // Update local presets cache so subsequent edits show the new path
            presets[timerId].output_file = result;
        } else {
            // null = user cancelled OR validation failed.
            // We can't distinguish — show a non-alarming message and point at logs.
            errorEl.textContent = 'No file selected, or selection rejected. Check logs for details.';
            errorEl.style.display = 'block';
        }
    });
```

- [ ] **Step 3: Add styling for the input-with-button layout in `frontend/css/style.css`**

Append to `frontend/css/style.css`:

```css
/* Input with adjacent button (e.g. file picker) */
.input-with-button {
    display: flex;
    gap: 8px;
}

.input-with-button input {
    flex: 1;
    min-width: 0;
}

.input-with-button button {
    flex-shrink: 0;
    white-space: nowrap;
}

.input-with-button input[readonly] {
    cursor: default;
    background: rgba(255, 255, 255, 0.06);
}
```

- [ ] **Step 4: Manual smoke test**

```bash
launch.bat
```

1. Open any preset's editor
2. Click Browse...
3. Native file dialog should open
4. Pick or type a `.txt` file path → editor should display the chosen path
5. Save the preset
6. Run the timer briefly and confirm it writes to the new path
7. Try Browse, then cancel the dialog → no error, displayed path unchanged
8. Try Browse, pick a path inside `C:\Windows\` → error message appears, path unchanged
9. Try Browse, pick a path that another preset already uses → error message appears

- [ ] **Step 5: Commit**

```bash
git add frontend/index.html frontend/js/app.js frontend/css/style.css
git commit -m "feat: add Browse button for output file path with native save dialog"
```

---

## Task 15: config.json — set default_finished_sound and add per-preset finished_sound

**Files:**
- Modify: `config.json`

- [ ] **Step 1: Update `config.json`**

Replace `config.json` with:

```json
{
  "websocket": {
    "host": "127.0.0.1",
    "port": 8059,
    "auth": null
  },
  "default_finished_sound": "C:\\Windows\\Media\\chimes.wav",
  "presets": [
    {
      "name": "Socials",
      "duration": 120,
      "end_message": "",
      "trigger_seconds": 30,
      "trigger_action": "Push The Button Reminder",
      "output_file": "output/socials.txt",
      "finished_sound": null
    },
    {
      "name": "Intro",
      "duration": 300,
      "end_message": "",
      "trigger_seconds": null,
      "trigger_action": null,
      "output_file": "output/intro.txt",
      "finished_sound": null
    },
    {
      "name": "Break",
      "duration": 600,
      "end_message": "",
      "trigger_seconds": null,
      "trigger_action": null,
      "output_file": "output/break.txt",
      "finished_sound": null
    },
    {
      "name": "Custom",
      "duration": 0,
      "end_message": "",
      "trigger_seconds": null,
      "trigger_action": null,
      "output_file": "output/custom.txt",
      "finished_sound": null
    }
  ],
  "window": {
    "minimize_to_tray": true
  }
}
```

- [ ] **Step 2: Manual smoke test — full end-to-end with sound**

```bash
launch.bat
```

1. Set the Custom preset duration to 5 seconds in the editor
2. Click Start
3. Watch `output/custom.txt` in VS Code or `Get-Content -Wait`
4. When the countdown hits 0:
   - You should HEAR `chimes.wav`
   - The file should show `00:00` for 5 seconds
   - Then the file should blank
5. Check `logs/klute-timer.log` — should see entries for "entering finishing state" and "hold elapsed, blanking"

- [ ] **Step 3: Commit**

```bash
git add config.json
git commit -m "feat: default finished sound to chimes.wav, add per-preset finished_sound field"
```

**Note:** `config.json` is currently untracked (per `git status` from earlier). After this commit it will be tracked. If you'd rather keep `config.json` user-local and provide a `config.json.example` template instead, that's a follow-up decision — out of scope for this plan.

---

## Task 16: README — operational notes section

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add the Operational Notes section**

Open `README.md`. Find the section just before the `## Support` block at the bottom (around line 60). Insert a new section before it:

```markdown
## Operational Notes

### Don't open output files in Windows Notepad while the app is running

Klute-Timer writes to its output `.txt` files via atomic rename. Notepad opens files with a `FILE_SHARE_READ`-only handle which silently breaks the atomic write — the writer logs the failure and the OBS source freezes on its last good value with no obvious cause.

Use one of these instead:
- **VS Code** — opens with shared read access, refreshes on file change
- **Notepad++** — same
- **PowerShell** — `Get-Content -Wait .\output\socials.txt` for a live tail

OBS GDI+ Text "from file" sources are fine — they poll without locking.

### OBS GDI+ Text source — recommended setting

For the OBS Text (GDI+) source pointing at a Klute-Timer output file: right-click the source → **Properties** → check **"Custom text extents"** → set fixed Width and Height. This prevents the source's bounding box from resizing if the file content length ever changes, which keeps your scene layout stable.

### Adjusting alert sound volume

Klute-Timer plays sounds via the Windows audio stack and does not have an in-app volume control. To make alerts louder or quieter:

1. Right-click the speaker icon in your system tray → **Open Volume Mixer**
2. Find the **Python** entry (it appears after Klute-Timer plays its first sound)
3. Adjust the slider — the setting persists across reboots

For per-preset volume control or to amplify a quiet source sound, edit the WAV in Audacity (Effect → Volume and Compression → Normalize, or → Amplify) and save it to `sounds/`, then set `finished_sound` in `config.json` to point at the amplified copy.

### Future packaging

The project currently launches via `python -m src.app` or `launch.bat` (a stopgap script in the project root). A real `KluteTimer.exe` build via PyInstaller is tracked as a follow-up.
```

- [ ] **Step 2: Verify the existing Support section is still there**

```bash
grep -A 3 "ko-fi.com/ktulue" README.md
```

Expected: the existing Support block with the Ko-fi link is unchanged.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add operational notes section to README"
```

---

## Final Verification

After all 16 tasks complete:

- [ ] **Run the full test suite**

```bash
pytest -v
```

Expected: all tests pass. No failures, no errors.

- [ ] **Manual smoke test checklist (from the spec)**

Run through items 1-15 from the "Manual smoke test checklist" section of `docs/superpowers/specs/2026-04-07-timer-polish-design.md`.

- [ ] **Branch is ready for review**

```bash
git log --oneline fix/output-file-lifecycle ^main
```

Expected: ~16 commits, one per task, plus the original spec commit.

The branch is ready for the user's review and (with their approval) a pull request against `main`. Per the user's global rule: **open the PR and stop. Do not run `gh pr merge` without explicit approval.**

---

## Spec Coverage Self-Review

Each spec section/requirement, mapped to its implementing task:

| Spec section | Tasks |
|---|---|
| Goals: Start/Pause behave correctly | Task 4 (implementation), Task 5 (regression test) |
| Goals: impossible to start with meaningless duration | Task 4 (implementation), Task 6 (regression test), Task 12 (GUI gating) |
| Goals: audible cue + visible 5s hold | Task 4 (state + hold), Task 8 (sound wiring), Task 15 (default sound) |
| Goals: out-of-the-box default sound | Task 15 (config.json default) |
| Goals: lock end_message | Task 9 (backend filter), Task 13 (frontend lock) |
| Goals: file picker for output paths | Task 10 (bridge), Task 14 (frontend button) |
| Goals: delete unreachable Reset code | Task 7 (Timer), Task 11 (Api) |
| Architecture: src/sound_player.py | Task 2 |
| Architecture: src/timer.py changes | Tasks 4, 5, 6, 7 |
| Architecture: src/config.py changes | Task 3 |
| Architecture: src/app.py changes | Tasks 8, 9, 10, 11 |
| Architecture: frontend changes | Tasks 12, 13, 14 |
| Architecture: config.json | Task 15 |
| Architecture: sounds/ directory | Task 1 |
| Architecture: README operational notes | Task 16 |
| State machine: all transitions | Task 4 (implementation covers full table) |
| Error handling: SoundPlayer never raises | Task 2 |
| Error handling: Timer callback wrapping | Task 4 (`_safe_call`), Task 6 (regression tests) |
| Error handling: file picker validation | Task 10 |
| Testing: test_timer.py additions | Tasks 4, 5, 6, 7 |
| Testing: test_sound_player.py | Task 2 |
| Testing: test_config.py additions | Task 3 |
| Testing: test_app_update_preset.py | Task 9 |
| Manual smoke test checklist | Final Verification section |

Coverage looks complete. No gaps.
