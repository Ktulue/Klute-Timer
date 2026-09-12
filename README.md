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

## Install

1. Get `KluteTimerSetup-<version>.exe`, either from a release or by building it
   yourself (see [Build the installer](#build-the-installer)).
2. Run it. No administrator rights are needed: Klute Timer installs for your
   Windows account only, into `%LOCALAPPDATA%\Programs\KluteTimer\`.
3. The installer is not code-signed, so Windows SmartScreen may say it
   "protected your PC" the first time. Click **More info**, then **Run anyway**.

The installer adds Klute Timer to the Start Menu and, unless you untick the
box, to your desktop. To upgrade, run a newer installer over the top: your
settings are kept. If Klute Timer is running, including minimized to the tray,
the installer asks you to close it first rather than stopping a live timer.

## Setup

### Requirements

- Windows 10 or 11
- Streamer.bot with WebSocket server enabled (default port: 8059)

### Run from source

For development, with Python 3.10+:

```bash
pip install -r requirements.txt
python -m src.app
```

### Build the installer

```bash
pip install -r requirements-dev.txt     # installs pyinstaller
winget install JRSoftware.InnoSetup     # one-time: Inno Setup 6.3 or later
build.bat
```

`build.bat` produces two things:

| Output | What it is |
| --- | --- |
| `dist\KluteTimer\KluteTimer.exe` | The app, as a one-folder PyInstaller build with `_internal\` beside it |
| `dist\installer\KluteTimerSetup-<version>.exe` | The installer that packages it |

Notes:

- The version lives in one place, `src/version.py`. The exe, the installer, the
  Installed apps entry, and the Settings panel all read it from there.
- **Nothing you own lives in `dist\`.** Your settings, logs, and the default
  output folder live in `%APPDATA%\KluteTimer\`, so rebuilding is always safe.
- Close Klute Timer before rebuilding if it is running from `dist\KluteTimer\`;
  a running exe holds its log file open and blocks the build.
- If you used a desktop shortcut from an older build and untick the desktop
  shortcut box while installing, that old shortcut still points at
  `dist\KluteTimer\`. Delete it.
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

Each preset writes to its own `.txt` file, and all four live together in one
folder. To find them, click **Settings** (the gear in the footer) — it shows the
full path to the output folder, an **Open Folder** button, and the exact file
each timer writes to:

| Timer | File |
|---|---|
| Socials | `socials.txt` |
| Intro | `intro.txt` |
| Break | `break.txt` |
| Custom | `custom.txt` |

All four files are created the moment the app starts, so you can point OBS at
them before a timer has ever run. For each one, add a **Text (GDI+)** source in
OBS, tick **Read from file**, and browse to it. The file updates every second
while that timer runs.

To keep the files somewhere else — outside the repo, or on a drive you back up —
use **Change Folder...** in Settings. The four files are created in the new
location immediately; re-point your OBS sources afterwards, since they keep
reading the old path until you do. The folder you choose is stored as an
absolute path, so rebuilding or moving the app won't relocate your files.

The output folder is also shown in the footer at all times, so you always know
where the app is writing.

## Where your files live

Everything you own lives in one folder, `%APPDATA%\KluteTimer\`. Paste that
into the Windows Explorer address bar to open it.

| What | Where |
| --- | --- |
| Settings | `%APPDATA%\KluteTimer\config.json` |
| Logs | `%APPDATA%\KluteTimer\logs\` |
| Timer text files, by default | `%APPDATA%\KluteTimer\output\` |

The output folder is the one OBS reads, and it is the one you can move. Use
**Settings > Change Folder...** to send the four `.txt` files somewhere more
convenient, such as `C:\Streaming\Overlays\`, and **Reset to Default** to send
them back. Either way the settings panel shows the full path of every file, with
a **Copy Path** button for pasting into the OBS file picker. Re-point your OBS
text sources afterwards, because moving the files does not move OBS with them.

The install folder, `%LOCALAPPDATA%\Programs\KluteTimer\`, holds only the
program. Installing, upgrading, or reinstalling never touches your data.

### Removing Klute Timer

Uninstall it from **Windows Settings > Apps > Installed apps**: find
**Klute Timer**, open the **...** menu, and choose **Uninstall**. Close the app
first if it is running, including from the tray.

The uninstaller removes the program, its Start Menu and desktop shortcuts, and
its Installed apps entry. It then asks whether to also delete your settings,
presets, logs, and timer text files in `%APPDATA%\KluteTimer\`:

- **No** (the default) keeps them, so a future reinstall picks up exactly where
  you left off.
- **Yes** deletes that folder.

A custom output folder you chose somewhere else, such as
`C:\Streaming\Overlays\`, is never deleted either way. A silent uninstall
(`/SILENT` or `/VERYSILENT`) keeps your data without asking.

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
2. Find the **Klute Timer** entry (or **Python** when running from source) — it
   appears after Klute-Timer plays its first sound
3. Adjust the slider — the setting usually persists across reboots. When
   running from source, this controls all Python processes on your machine
   (any other Python script using audio will share the same slider)

For per-preset volume control or to amplify a quiet source sound, edit the WAV
in Audacity (Effect → Volume and Compression → Normalize, or → Amplify) and
save it somewhere of your own, such as `%APPDATA%\KluteTimer\sounds\`, then
set `finished_sound` in `config.json` to that file's full (absolute) path.
The install folder is replaced on upgrade, so a copy saved there would not
survive one.

### Packaging

For day-to-day development the app launches via `python -m src.app` or
`launch.bat`. To install it like any other Windows app, build and run the
installer — see [Build the installer](#build-the-installer) under Setup.

---

## Support

☕ [Buy me a coffee on Ko-fi](http://ko-fi.com/ktulue)

Created by Ktulue | The Water Father 🌊
