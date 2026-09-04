# Klute Timer

Stream timer app replacing the defunct Elk Timer. Python desktop GUI with Streamer.bot WebSocket integration and text file output for OBS.

## Features

- 4 configurable timer presets (3 defaults + 1 custom)
- Streamer.bot WebSocket integration for Stream Deck triggering
- Text file output for OBS GDI+ text sources
- Configurable trigger points (fire Streamer.bot actions at N seconds remaining)
- Audible alert on timer expiry (chimes.wav default, per-preset override via `config.json`)
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

### Build the standalone app (KluteTimer.exe)

To run Klute Timer by double-clicking a desktop shortcut — no Python or `pip`
required on the target machine — build a standalone executable with PyInstaller:

```bash
pip install -r requirements-dev.txt   # installs pyinstaller
build.bat                             # produces dist\KluteTimer\KluteTimer.exe
```

Then create a desktop shortcut pointing at it:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\create_shortcut.ps1
```

Notes:

- The build is a one-folder bundle: `dist\KluteTimer\KluteTimer.exe` plus an
  `_internal\` folder. **Keep them together** — the shortcut points at the exe,
  so you never interact with `_internal\` directly.
- `config.json`, `output\`, `logs\`, and `sounds\` live **next to the exe** in
  `dist\KluteTimer\`, so presets stay editable and OBS can read the output files.
- Rebuilding recreates `dist\KluteTimer\`, resetting its `config.json` to the
  repo default. Back up a customized config before rebuilding.
- The app icon is generated from `scripts\make_icon.py` (committed as
  `assets\KluteTimer.ico`); rerun it only if you change the icon design.

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
- Timer presets (name, duration, trigger points, `finished_sound` override)
- Window behavior (minimize to tray)

## License

MIT

## Operational Notes

### Don't open output files in Windows Notepad while the app is running

Klute-Timer writes to its output `.txt` files via atomic rename. Notepad opens files without `FILE_SHARE_DELETE`, which silently blocks the atomic rename — the writer logs the failure and the OBS source freezes on its last good value with no obvious cause.

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
3. Adjust the slider — the setting usually persists across reboots, but note this controls all Python processes on your machine (any other Python script using audio will share the same slider)

For per-preset volume control or to amplify a quiet source sound, edit the WAV in Audacity (Effect → Volume and Compression → Normalize, or → Amplify) and save it to `sounds/`, then set `finished_sound` in `config.json` to point at the amplified copy.

### Packaging

For day-to-day development the app launches via `python -m src.app` or
`launch.bat`. For a double-click desktop app, build the standalone
`KluteTimer.exe` — see [Build the standalone app](#build-the-standalone-app-klutetimerexe) under Setup.

---

## Support

☕ [Buy me a coffee on Ko-fi](http://ko-fi.com/ktulue)

Created by Ktulue | The Water Father 🌊
