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
