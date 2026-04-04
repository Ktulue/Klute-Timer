# Klute-Timer Design Spec

> Date: 2026-04-04
> Status: Approved
> Approach: B (Layered Modules)
> Tier: Bicycle (ship target)

## Overview

A Python desktop app that replaces the defunct Elk Timer. Provides countdown timers for Twitch/YouTube streamers with Streamer.bot WebSocket integration for Stream Deck triggering and text file output for OBS GDI+ text sources.

The core differentiator is Streamer.bot-native integration -- no existing tool combines WebSocket listener + Stream Deck triggering + text file output + GUI in a single purpose-built application.

## Tech Stack

- **Language:** Python
- **GUI Framework:** pywebview (MIT licensed, ~2MB)
- **Frontend:** HTML/CSS/JS rendered in OS webview (Edge WebView2 on Windows)
- **WebSocket:** Python `websockets` library
- **Config:** JSON file (Python `json` stdlib)
- **Logging:** Python `logging` stdlib with rotating file handler
- **License:** MIT

## Project Structure

```
klute-timer/
├── src/
│   ├── app.py              # Entry point, pywebview setup, JS bridge
│   ├── timer.py            # Timer class (countdown logic, state management)
│   ├── ws_client.py        # Streamer.bot WebSocket client
│   ├── file_writer.py      # Text file output for OBS
│   ├── config.py           # JSON config load/save
│   └── logger.py           # Logging setup and configuration
├── frontend/
│   ├── index.html          # Main UI layout
│   ├── css/
│   │   └── style.css       # Dark aquatic theme
│   └── js/
│       └── app.js          # Frontend logic, pywebview bridge calls
├── config.json             # User config (created on first run with defaults)
├── logs/                   # Rotating log files
├── output/                 # Default text file output directory
├── requirements.txt        # pywebview, websockets
└── README.md
```

## Module Design

### `timer.py` -- Timer Class

Each timer is an independent instance.

**States:** `idle`, `running`, `paused`, `finished`

**Properties:**
- `name` -- display name (editable)
- `duration` -- total seconds
- `remaining` -- current seconds remaining
- `end_message` -- custom text shown/written when timer hits zero
- `trigger_point` -- optional: seconds remaining at which to fire a Streamer.bot action
- `trigger_action` -- optional: Streamer.bot action name to fire at trigger point
- `output_file` -- path to the text file this timer writes to

**Methods:** `start()`, `pause()`, `resume()`, `stop()`, `reset()`

**Tick behavior:**
- Decrements every 1 second while in `running` state
- Each tick notifies the app (file writer updates, frontend updates)
- When remaining hits the trigger point, notifies the app to fire the configured Streamer.bot action
- When remaining hits zero, state transitions to `finished`

**Display format (adaptive):**
- Original duration under 1 hour: `MM:SS` (e.g., `04:23`)
- Original duration 1 hour or above: `HH:MM:SS` (e.g., `01:04:23`)
- Format is locked to the original duration, not the remaining time (a 2-hour timer doesn't switch format when it crosses below 1 hour)

**Threading:** Each timer runs its own thread with a 1-second sleep loop. Thread-safe state access via a lock.

### `ws_client.py` -- Streamer.bot WebSocket Client

Connects to Streamer.bot's built-in WebSocket server as a client.

**Connection:**
- Default: `ws://127.0.0.1:8059` (configurable via config.json)
- Subscribes to Custom events on connect

**Inbound commands (Streamer.bot -> Timer App):**

| Command | Payload | Behavior |
|---------|---------|----------|
| `start` | `{"command": "start", "timer": 1}` | Starts timer by preset index (1-based) |
| `start` | `{"command": "start", "timer": 1, "duration": 120}` | Starts with override duration |
| `pause` | `{"command": "pause", "timer": 1}` | Pauses if running, resumes if paused |
| `stop` | `{"command": "stop", "timer": 1}` | Stops and resets timer |

Timer index maps to preset position (1-4).

**Outbound commands (Timer App -> Streamer.bot):**

When a timer's trigger point fires (e.g., 30 seconds remaining on the socials timer), sends a `DoAction` request:

```json
{"request": "DoAction", "action": {"name": "Push The Button Reminder"}, "id": "trigger-123"}
```

The action name is whatever the user configures in the trigger point settings.

**Reconnection:**
- On disconnect, retries silently with exponential backoff
- After 5 consecutive failures, surfaces a notification to the GUI
- Resets failure count on successful reconnect

**Error handling:**
- Unknown command: ignored, logged
- Invalid timer index: ignored, logged
- Outbound action not found: Streamer.bot returns error, app logs it silently

### `file_writer.py` -- OBS Text File Output

- One file per timer, enforced (no two timers can share a file path)
- On each tick: writes formatted time to the file (adaptive MM:SS or HH:MM:SS)
- On finish: writes the custom end message (or blank if none configured)
- On stop/idle: clears the file (writes empty string)
- Writes are atomic (write to temp file, then rename) to prevent OBS from reading half-written data
- Default output directory: `output/` subfolder alongside the app
- 1-second write cadence matching timer tick

### `config.py` -- Configuration Persistence

Loads and saves a JSON config file. Created with sensible defaults on first run.

**Config structure:**
```json
{
  "websocket": {
    "host": "127.0.0.1",
    "port": 8059,
    "auth": null
  },
  "presets": [
    {
      "name": "Socials",
      "duration": 120,
      "end_message": "",
      "trigger_seconds": 30,
      "trigger_action": "Push The Button Reminder",
      "output_file": "output/socials.txt"
    },
    {
      "name": "Intro",
      "duration": 300,
      "end_message": "",
      "trigger_seconds": null,
      "trigger_action": null,
      "output_file": "output/intro.txt"
    },
    {
      "name": "Break",
      "duration": 600,
      "end_message": "",
      "trigger_seconds": null,
      "trigger_action": null,
      "output_file": "output/break.txt"
    },
    {
      "name": "Custom",
      "duration": 0,
      "end_message": "",
      "trigger_seconds": null,
      "trigger_action": null,
      "output_file": "output/custom.txt"
    }
  ],
  "window": {
    "minimize_to_tray": true
  }
}
```

- Presets are editable at runtime and saved on change
- All 4 presets are fully modifiable (name, duration, end message, trigger, output path)
- 3 ship with defaults (Socials 2min, Intro 5min, Break 10min), 1 starts unconfigured

### `logger.py` -- Logging System

Uses Python's built-in `logging` module with rotating file handler.

**Log file:** `logs/klute-timer.log`
- Rotated by size (5MB cap)
- Keeps last 3 rotated files

**Log entry format:**
```
2026-04-04T18:32:15.442Z | ERROR | ws_client | context: processing inbound command {"command":"start","timer":5} | error: timer index 5 out of range (4 presets configured) | state: ws=connected, timers=[idle,running,idle,idle]
```

**Each entry captures:**
- Timestamp (ISO 8601)
- Severity (DEBUG, INFO, WARNING, ERROR)
- Pipeline location (which module: `ws_client`, `timer`, `file_writer`, `config`, `app`)
- Action context (what was happening before the error)
- Error detail (exception/failure message)
- State snapshot (relevant system state at time of error)

**GUI log viewer:** Accessible from the app via a button/menu. Shows recent log entries with severity filtering. Not front-and-center, but available for post-stream diagnosis.

### `app.py` -- Entry Point and Bridge

- Creates the pywebview window pointed at `frontend/index.html`
- Exposes a JS API class for the frontend to call:
  - `start_timer(id)`, `pause_timer(id)`, `stop_timer(id)`, `reset_timer(id)`
  - `update_preset(id, data)` -- modify preset at runtime
  - `get_state()` -- returns all timer states and connection status
  - `save_config()` -- persist current config to disk
  - `get_logs(severity, count)` -- fetch recent log entries for the viewer
- Starts the WebSocket client on launch
- Routes timer tick updates to the frontend via `evaluate_js()`
- Handles system tray integration (minimize, restore, quit)

## Frontend Design

### Layout

Single window, two zones:

- **Status bar (top):** Streamer.bot connection indicator with text label (Connected / Disconnected / Reconnecting). Always visible.
- **Timer panel (main area):** 4 timer cards, no scrolling needed.

### Timer Card

Each card displays:
- Preset name (editable inline)
- Countdown display -- large monospace text, adaptive format
- State label (Idle / Running / Paused / Finished)
- Controls: Start, Pause, Stop buttons
- Edit access (gear icon or expandable): duration, end message, trigger point, output file path

### Theme

- **Background:** Deep navy/charcoal (#0d1117 range)
- **Cards:** Slightly lighter dark panels (#161b22 range) with subtle borders
- **Accent/interactive:** Teal
- **State colors (always paired with text labels):**
  - Teal -- running
  - Amber -- paused
  - Cool gray -- idle
  - Red -- finished
- **Timer text:** Large, monospace, high-contrast white
- **Labels/controls:** Clean sans-serif

### System Tray

- Minimize-to-tray via window control
- Tray icon with right-click menu: Show, Quit
- Timers continue running while minimized

### Accessibility

- WCAG AA contrast ratios on all text
- All controls keyboard-navigable
- State communicated via color + text label (never color alone)

## Bicycle Tier Success Criteria

- [ ] GUI with 4 timer cards (3 default presets + 1 custom), all editable
- [ ] Start/pause/stop/reset per timer from GUI
- [ ] Stream Deck button -> Streamer.bot action -> timer starts/pauses/stops
- [ ] Timer trigger points fire Streamer.bot actions (e.g., 30-sec "push the button")
- [ ] Adaptive display format (MM:SS or HH:MM:SS based on original duration)
- [ ] Custom end messages per timer
- [ ] Each timer writes to its own text file, OBS reads in real time
- [ ] Blank file when timer is idle
- [ ] Atomic file writes
- [ ] WebSocket auto-reconnect (silent for 5 failures, then notify)
- [ ] JSON config persists presets and settings between sessions
- [ ] Rotating log files with pipeline context, viewable in-app
- [ ] Dark aquatic theme matching streaming ecosystem aesthetic
- [ ] Minimize to system tray, timers continue running
- [ ] Runs reliably for a full stream session (3-6 hours)
- [ ] MIT licensed

## Deferred (Car Tier)

- Sound alerts on timer completion
- Count-up mode
- "Show only active timer" OBS output logic
- Configurable output paths UI (currently editable in config but no file picker)
- Stream Deck support with multiple actions per timer
- Additional timer slots beyond 4

## The Real Test

You use it on your own stream for a full session and don't switch back to whatever workaround you're using now.
