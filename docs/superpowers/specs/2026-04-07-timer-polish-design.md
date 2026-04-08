# Timer Polish — Design Spec

**Date:** 2026-04-07
**Branch:** `fix/output-file-lifecycle`
**Status:** Draft, awaiting user review

## Background

During hands-on testing of the first Klute-Timer build, four problems surfaced:

1. Pressing **Start** on a paused timer restarts it from full duration instead of resuming. Confirmed in `src/timer.py:67-84` — `start()` unconditionally resets `_remaining = self._duration` whenever state isn't `running`.
2. The **Custom** preset (which has `duration: 0` in `config.json`) accepts a Start press and the countdown ticks into negative values, briefly displaying `-1:59` before the finish handler kicks in.
3. When a timer reaches `00:00`, the OBS text source goes blank instantly with no audible or visible cue. The streamer can miss the moment entirely.
4. When the file content changed length (e.g. `02:00` → `Time's Up!`), the OBS GDI+ Text source's bounding box resized and broke the on-stream layout.

This spec covers the fixes for #1 and #2, adds an end-of-timer notification system to address #3, locks down the unconfirmed `end_message` feature so it can't cause #4 in this build, and folds in a small file-picker convenience that emerged during the brainstorm.

## Goals

- Make Start/Pause behave the way every other timer app does: Pause freezes, Start resumes from where Pause left off.
- Make it impossible to start a timer with a meaningless duration.
- Give the streamer an unmissable audible cue when a timer expires, plus a visible 5-second `00:00` hold in OBS so the moment is preserved on stream.
- Default to a working out-of-the-box sound (no user setup) but allow per-preset overrides.
- Lock the `end_message` text feature so nothing can be saved into a field whose downstream behavior we don't yet trust.
- Let the streamer point each preset at any output file path on disk via a native file picker, without hand-editing `config.json`.
- Delete the unreachable `Reset` code paths so the codebase reflects the actual feature surface.

## Non-Goals (deferred)

- **End message text feature** — paused. Field remains in `config.json` for forward compat but is unwritten by code and locked in the UI. Returning in a future build once we've nailed down the desired display behavior.
- **GUI flash / in-window animation** on timer expiry — sound + visible 5-second hold is sufficient.
- **Trigger-point sounds in Klute** — already handled by existing `Streamer.bot` `Push The Button Reminder` action via `Timer.on_trigger` → `ws_client.trigger_action`. No code change.
- **In-app volume control / per-preset volume / MP3 / OGG support** — `winsound` has no volume API and that's an accepted trade-off for tonight. Volume is managed via Windows Volume Mixer. Future: switch to `pygame.mixer` if per-preset volume becomes a real felt need.
- **Configurable hold duration** — hardcoded to 5 seconds, constructor-injectable for testability. Revisit if 5s feels wrong after live use.
- **Reset button** — feature deleted entirely. Stop already does "halt + reset duration + clear file" combined. Restart-from-beginning is two clicks (Stop → Start). Re-add as a follow-up branch only if the friction is real after live use.
- **PyInstaller `.exe` build** — tracked separately as a project memory follow-up. Stopgap is the `launch.bat` already created in the project root.

## Architecture

### New module: `src/sound_player.py`

Thin wrapper around `winsound.PlaySound`. Public API:

```python
class SoundPlayer:
    def play(self, path: Optional[str]) -> None: ...
```

**Critical contract: `play()` MUST never raise.** All exceptions caught, logged, swallowed. The timer's run thread is upstream of this and a sound failure cannot be allowed to crash the timer.

Behavior:
- `path` is `None` or empty → silent return, no log
- Path doesn't exist on disk → log WARNING, return
- File isn't a valid WAV / `winsound` raises → log ERROR, return
- Plays via `winsound.PlaySound(path, SND_FILENAME | SND_ASYNC)`
- A new `play()` call interrupts any sound currently playing — accepted behavior, useful for "two timers expire close together"

Logger namespace: `klute_timer.sound_player`. Module is ~25 lines and stateless.

### Modified: `src/timer.py`

**1. New `finishing` state** added to the state machine. Sits between `running` and `finished`. During this state, `_remaining == 0`, the OBS file holds `00:00` (already written by the last `_on_tick`), and the run thread is in a cancellable `stop_event.wait(hold_seconds)` loop.

**2. `start()` learns to branch by source state:**
- From `idle` or `finished` → reset `_remaining = duration`, spawn run thread (current behavior, unchanged)
- From `paused` **(this is the bug fix)** → do NOT reset `_remaining`; clear `stop_event`; spawn new run thread that picks up where the old one left off
- From `running` → no-op (current behavior, unchanged)
- From `finishing` → cancel the hold (set `stop_event`); reset `_remaining = duration`; spawn new run thread. The new countdown's first tick overwrites the file, so no separate clear is needed.
- If `duration <= 0` → log WARNING, return without state change

**3. New `on_blank` callback** fired when the hold elapses naturally. App handler clears the OBS file. If the hold is cancelled by Stop/Start, `on_blank` does NOT fire — the cancelling handler manages file state itself.

**4. `hold_seconds` constructor parameter** with default `5`. Tests pass `0.1` for fast assertions; production stays at `5`. Not user-configurable in `config.json` for now.

**5. Callback exception wrapping** — all callback invocations (`on_tick`, `on_finish`, `on_trigger`, new `on_blank`) wrapped in `try/except` so a downstream raise (e.g. transient `OSError` from the file writer) cannot kill the run thread.

**6. Delete `Timer.reset()`** (currently `src/timer.py:128-130`) — dead code with no UI affordance.

### Modified: `src/config.py`

**New fields, both backward-compatible defaults to `None`:**
- `Preset.finished_sound: Optional[str]` — path to a per-preset WAV
- `Config.default_finished_sound: Optional[str]` — top-level fallback path

Existing `config.json` files without these fields load fine.

### Modified: `src/app.py`

**1. Construct one `SoundPlayer`** in `Api.__init__` and stash on `self`.

**2. `_on_finish` now plays the sound** instead of writing `end_message`:
```python
def _on_finish(self, timer_id: int) -> None:
    preset = self._config.presets[timer_id]
    sound = preset.finished_sound or self._config.default_finished_sound
    self._sound_player.play(sound)
    self._push_timer_update(timer_id)
```
The `end_message` write is removed entirely.

**3. New `_on_blank` callback** wired into Timer construction. Handler:
```python
def _on_blank(self, timer_id: int) -> None:
    self._file_writer.clear(timer_id)
    self._push_timer_update(timer_id)
```

**4. New JS bridge method `pick_output_file`:**
```python
def pick_output_file(self, timer_id: int) -> Optional[str]:
    """Open a native Save-dialog file picker for the given preset's output file.
    Returns the chosen path on success, None on cancel or validation failure.
    Validates writability before committing the change."""
```
- Opens `webview.SAVE_DIALOG` (allows picking existing files OR typing new ones)
- File type filter: `*.txt`
- Validates: parent dir exists, parent dir is writable (`os.access(parent, os.W_OK)`), no collision with another preset's `output_file`
- On success, calls `update_preset(timer_id, {"output_file": path})` and returns the path
- On cancel or validation failure, returns `None`. Frontend renders inline error from a returned reason string (TBD: simple `(path, error)` tuple or just log + None — pick during implementation)

**5. `update_preset` rejects `end_message` updates** with a defense-in-depth filter: if `updates` contains `end_message`, drop the key and log a warning. Two lines, locks the contract even if frontend is bypassed.

**6. Delete `Api.reset_timer()`** (currently `src/app.py:161-164`) — dead code.

### Modified: `frontend/js/*.js` (preset editor)

Exact file pending inspection during implementation.

**1. New "Browse..." button** next to the output file display in the preset editor. Click handler calls `pywebview.api.pick_output_file(timer_id)`. On success, updates the displayed path. On failure, shows inline error.

**2. Visible current output path** as a read-only label so the user can see what each preset is writing to.

**3. End Message field is locked:** `disabled` attribute on the input, greyed-out styling, helper text *"Paused — returning in a future update"*.

**4. Start button is `disabled`** when the preset's duration is 0 or empty. Re-enabled when duration becomes valid via the preset edit flow.

**5. No Reset button** to add. If any handler exists referencing `pywebview.api.reset_timer`, remove it (likely zero hits — there's no button currently).

### Modified: `config.json`

```json
{
  "websocket": { ... },
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
    ...
  ],
  "window": { ... }
}
```

The `default_finished_sound` defaults to a Windows system WAV that's guaranteed to exist on every Windows install. Per-preset `finished_sound` fields default to `null` (use the global). Existing `end_message` values are preserved untouched (data preserved for future re-enable, but unread by code).

### New: `sounds/` directory

Project-root `sounds/` directory with a `.gitkeep` file. The directory itself is committed; user-supplied WAVs live here. Add `sounds/*.wav` to `.gitignore` (but not `sounds/.gitkeep`).

### Modified: `README.md`

New "Operational Notes" section:

- **Notepad locking:** Don't open `output/*.txt` files in Windows Notepad while the app is running. Notepad's `FILE_SHARE_READ`-only handle silently breaks atomic writes. Use VS Code, Notepad++, or `Get-Content -Wait` in PowerShell instead.
- **OBS Custom text extents:** Recommended for the GDI+ Text source pointing at output files. Right-click source → Properties → check "Custom text extents" → set fixed Width/Height. This prevents layout shifts if the file content length ever changes (defensive — currently the file only contains fixed-width `MM:SS` or empty).
- **Adjusting alert sound volume:** Klute-Timer plays sounds via the Windows audio stack and does not have an in-app volume control. To make alerts louder or quieter, right-click the speaker icon → Open Volume Mixer → find the Python entry → adjust the slider. The setting persists across reboots. For per-preset volume control, use a pre-amplified custom WAV in `sounds/`.

## State Machine

### States

| State | Meaning | `_remaining` | Thread alive? | OBS file content |
|---|---|---|---|---|
| `idle` | Initial / after Stop | = duration | no | empty |
| `running` | Countdown active | decrementing | yes | live `MM:SS` |
| `paused` | Countdown frozen | preserved | no | frozen `MM:SS` |
| `finishing` | Hit 0, sound played, holding `00:00` for `hold_seconds` | 0 | yes (in `wait()` loop) | `00:00` |
| `finished` | Terminal — hold elapsed, file blanked | 0 | no | empty |

### Transition table

| From | Event | To | Side effects |
|---|---|---|---|
| `idle` | Start (duration > 0) | `running` | Reset `_remaining = duration`; spawn run thread |
| `idle` | Start (duration ≤ 0) | `idle` | Log warning, no-op |
| `running` | Pause | `paused` | Signal stop event; thread exits; `_remaining` preserved |
| `running` | Stop | `idle` | Signal stop event; reset `_remaining`; clear file |
| `running` | (countdown reaches 0) | `finishing` | Play sound; begin cancellable `wait(hold_seconds)` |
| `paused` | Start **(bug fix)** | `running` | **Do not reset `_remaining`**; clear stop event; spawn new run thread |
| `paused` | Stop | `idle` | Reset `_remaining`; clear file |
| `finishing` | (hold elapses naturally) | `finished` | Fire `on_blank` → app clears file |
| `finishing` | Stop | `idle` | Cancel hold; reset `_remaining`; clear file |
| `finishing` | Start | `running` | Cancel hold; reset `_remaining = duration`; spawn new run thread (first tick overwrites file, no flicker) |
| `finishing` | Pause | `finishing` | Silent no-op |
| `finished` | Start | `running` | Reset `_remaining = duration`; spawn run thread |
| `finished` | Stop | `idle` | Reset `_remaining`; file already blank, no-op write |
| `finished` | Pause | `finished` | Silent no-op |

All Reset transitions are removed. The `Timer.reset()` and `Api.reset_timer()` methods are deleted.

### Concurrency

- The hold uses `stop_event.wait(hold_seconds)` which is cancellable by any caller of `pause()`/`stop()`/`start()` — they all signal the same `_stop_event`. `wait()` returns `True` if cancelled, `False` if timeout elapsed naturally.
- All state transitions happen under `self._lock` exactly as they do today. The hold's `wait()` does NOT hold the lock — that would deadlock anything inspecting state during the hold.
- Callbacks fire OUTSIDE the lock (existing pattern, unchanged) so callbacks can call back into the timer without recursive lock acquisition.

## Data Flow — Timer Hits 0

```
[run loop] decrements _remaining to 0
    │
    ▼
fires on_tick(timer_id, 0)
    │
    ▼
app._on_tick → file_writer.write_time(0, "00:00")     ← OBS sees 00:00
    │
    ▼
[run loop] sees remaining <= 0, transitions: state = "finishing"
    │
    ▼
fires on_finish(timer_id)
    │
    ▼
app._on_finish → sound_player.play(preset.finished_sound or default)   ← sound starts
    │
[run loop] enters hold: stop_event.wait(hold_seconds)
    │
    ├── (hold elapses naturally) ──────────┐
    │                                       ▼
    │                              state = "finished"
    │                                       │
    │                                       ▼
    │                              fires on_blank(timer_id)
    │                                       │
    │                                       ▼
    │                              app._on_blank → file_writer.clear(0)   ← file blanks
    │                                       │
    │                                       ▼
    │                              push GUI state update
    │                                       │
    │                                       ▼
    │                                  [thread exits]
    │
    └── (cancelled by Stop/Start) ──────────┐
                                             ▼
                                  [respective handler manages file state]
                                             │
                                             ▼
                                        [thread exits]
```

## Error Handling

### `SoundPlayer`

| Failure | Behavior | Log level |
|---|---|---|
| `path` is `None` or empty | Silent no-op | — |
| Path doesn't exist | Log + no-op | WARNING |
| Invalid WAV / `winsound` raises | Log + no-op | ERROR |
| Audio device unavailable | Log + no-op | ERROR |

**Contract:** `SoundPlayer.play()` MUST NEVER raise. Top-level try/except catches every exception.

### `Timer`

| Failure | Behavior |
|---|---|
| Start with `duration <= 0` | Log warning, no state change |
| Start from `running` | Existing no-op |
| Pause from non-`running` (including `finishing`) | Existing no-op (silent) |
| `on_finish` callback raises | Caught by run loop, logged, hold still proceeds |
| `on_blank` callback raises | Caught, logged, state still transitions to `finished` |
| Stop signaled mid-`wait()` | Wait returns `True`; skip blank write; let interrupting handler manage state |

### File picker

| Failure | Behavior |
|---|---|
| User cancels dialog | Return `None`, frontend leaves path unchanged |
| Parent dir doesn't exist | Validation rejects, log warning, return `None`, frontend shows inline error |
| Write-protected location | Same as above |
| Invalid path characters | Same as above |
| Collision with another preset | `FileWriter.register` raises `ValueError` (existing behavior, line 19-21); catch in bridge, return `None`, show inline error |

### Logging conventions

All new log lines follow the existing pattern:
```python
log.warning(
    "...",
    extra={"context": "...", "state": "..."},
)
```
matching `src/timer.py:81-84` and `src/file_writer.py:65-71`. New logger namespace: `klute_timer.sound_player`.

## Testing

### Unit tests — `tests/test_timer.py` (existing file, additions)

| Test | Verifies |
|---|---|
| `test_start_from_paused_resumes` | Pause at remaining=15, call Start, assert remaining ≈ 15 not 30 (bug fix) |
| `test_start_with_zero_duration_rejected` | duration=0, Start, assert state stays `idle`, warning logged (bug fix) |
| `test_start_with_negative_duration_rejected` | Defensive — reject < 0 same as = 0 |
| `test_finishing_state_holds_for_hold_seconds` | duration=1, hold_seconds=0.1; assert `running → finishing` then after ~0.1s `finishing → finished` |
| `test_finishing_cancelled_by_stop` | Reach `finishing`, call Stop within hold, assert state `idle`, `on_blank` NOT fired |
| `test_finishing_cancelled_by_start` | Reach `finishing`, call Start within hold, assert state `running` with full duration |
| `test_pause_during_finishing_is_noop` | Reach `finishing`, call Pause, assert state still `finishing`, hold continues |
| `test_on_finish_callback_exception_does_not_crash_thread` | Pass `on_finish` that raises, assert hold still proceeds and `on_blank` still fires |
| `test_reset_method_removed` | `assert not hasattr(timer, 'reset')` — defensive guard so it can't quietly come back |

The 5-second hold is exercised at `hold_seconds=0.1` via the new constructor parameter. Production timers stay at the default 5.

### Unit tests — `tests/test_sound_player.py` (new file)

| Test | Verifies |
|---|---|
| `test_play_with_none_path_is_silent` | `play(None)` returns, no error, no log |
| `test_play_with_empty_string_is_silent` | `play("")` returns, no error, no log |
| `test_play_with_missing_file_logs_warning` | `play("nonexistent.wav")` → WARNING, no exception |
| `test_play_with_invalid_wav_logs_error` | Mock `winsound.PlaySound` to raise; assert ERROR, no exception |
| `test_play_never_raises` | Parametrized — every failure mode above must return cleanly |

`winsound.PlaySound` patched via `unittest.mock.patch('winsound.PlaySound')` for failure modes. The "play never raises" test is the load-bearing contract the timer thread depends on.

### Unit tests — `tests/test_config.py` (existing file, additions)

| Test | Verifies |
|---|---|
| `test_preset_loads_with_finished_sound` | New field deserializes |
| `test_preset_loads_without_finished_sound_defaults_to_none` | Backward-compat |
| `test_config_loads_default_finished_sound` | New top-level field deserializes |
| `test_config_loads_without_default_finished_sound` | Backward-compat |
| `test_update_preset_rejects_end_message_updates` | Backend filter — `update_preset({"end_message": "x"})` is dropped with warning |

### Manual smoke test checklist (run before tomorrow's stream)

1. **Launch via `launch.bat`** — window opens, no errors
2. **Pause/resume bug** — start a 60s timer, pause at ~30s, hit Start, confirm resume from ~30s
3. **Duration zero bug** — set Custom duration to 0, confirm Start button disabled in GUI
4. **5-second hold** — start a 10s timer, watch the output file, confirm `00:00` shows for 5s then blanks
5. **Default sound on finish** — drop a short timer, confirm `chimes.wav` plays at the moment of `00:00`
6. **Per-preset sound override** — set `finished_sound` on one preset to a different WAV, confirm override
7. **Stop interrupts hold** — during the 5-second hold, hit Stop, confirm file blanks immediately
8. **Start interrupts hold** — during hold, hit Start on same preset, confirm new countdown begins
9. **File picker — relative path** — Browse, pick a path inside `output/`, confirm preset updates and next run writes there
10. **File picker — absolute path** — Browse, pick a path in a different folder, confirm validation passes
11. **File picker — write-protected location** — try `C:\Windows\`, confirm validation rejects with inline error
12. **File picker — collision with another preset** — try a path another preset uses, confirm rejection
13. **End message field locked** — open preset editor, confirm field disabled with "Paused" label
14. **OBS smoke test** — point a GDI+ Text source at an output file, run a timer end-to-end, confirm countdown + 5s hold + blank
15. **Streamer.bot smoke test** (if Streamer.bot is up) — fire Start/Stop commands from Streamer.bot, confirm timer responds

### Tests we are NOT writing

- pywebview file dialog interactions (native OS, can't reasonably automate)
- OBS GDI+ rendering (manual #14 covers it)
- `winsound` actual audio output to speakers (manual #5 covers it)
- ws_client / Streamer.bot integration (no scope changes; existing tests cover it)

## Open Questions / TBD During Implementation

- **Frontend file location for the preset editor changes** — to be confirmed by reading `frontend/js/*.js` during implementation. Section 2 references "preset editor JS" generically.
- **File picker error reporting from backend to frontend** — `pick_output_file` returns `Optional[str]`: the chosen path on success, `None` on cancel OR validation failure. The bridge logs the specific reason (cancelled / parent missing / not writable / collision) at WARNING level. The frontend shows a generic inline "Could not select file — see logs for details" message on `None`. This keeps the bridge signature simple and pushes diagnostic detail to the log file where the user can copy/paste it if reporting an issue.
- **`.gitignore` entry** — add `sounds/*.wav` (but keep `sounds/.gitkeep`) so user audio assets aren't committed.

## Out of Scope (explicit list, future work)

- End message text feature (paused, locked in UI, will return in a future build with a proper display semantic spec)
- GUI flash / animation on timer expiry
- pygame.mixer migration / per-preset volume / MP3 support
- Configurable hold duration via config.json
- Reset button (deleted; consider re-adding only if friction emerges in live use)
- PyInstaller `.exe` build (tracked as project memory follow-up)
- Trigger-point sounds in Klute (handled by Streamer.bot)
- File-writer health surfacing in GUI (silent failure on disk-full / removed-volume is acceptable for now)
