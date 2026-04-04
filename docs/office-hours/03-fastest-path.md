# Fastest Path

> Office Hours — Builder Mode
> Date: 2026-04-04
> Phase: B3 — Fastest Path to Something Usable

## Context
The user arrived with a fully formed skateboard/bicycle/car breakdown. This phase validated and captured that spec.

## Findings
The user provided a pre-existing spec with three tiers:

### Skateboard
- Python CLI that accepts a timer duration
- Counts down and writes to a `.txt` file that OBS reads
- Single timer only

### Bicycle
- Lightweight GUI with preset timer buttons
- Multiple simultaneous timers writing to separate text files
- Streamer.bot WebSocket integration for remote triggering

### Car
- Stream Deck support via Streamer.bot actions
- Customizable timer presets
- Sound alerts on completion
- Pause/resume functionality
- Count-up mode
- Configurable output paths

### Tech Stack
- **Language:** Python
- **GUI:** Tkinter or PyQt
- **Integration:** WebSocket (Streamer.bot)
- **Output:** Text files read by OBS GDI+ text sources

### Origin
Replaces the dead **Elk Timer** by TotallyNotAnElk (MIT licensed, no longer maintained or downloadable).

## Key Takeaways
- The spec is well-formed — no need to re-derive scope during brainstorming
- Multiple timers may not need to be simultaneous at first, but the architecture should support it
- The Bicycle tier is the minimum interesting product — CLI alone isn't shareable
