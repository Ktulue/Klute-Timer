# Core Delight

> Office Hours — Builder Mode
> Date: 2026-04-04
> Phase: B1 — What's Cool

## Context
Understanding what makes this timer project exciting and worth building — the "whoa" factor that separates it from generic countdown tools.

## Findings
The user identified **deep streaming integration** as the core delight — not visual spectacle or unique timer mechanics. Specifically:

- **Stream Deck button press** triggers the timer via Streamer.bot
- **Streamer.bot WebSocket** receives the command and relays to the timer app
- **Timer app** manages the countdown and writes to a text file
- **OBS GDI+ text source** reads the file and displays on stream

The pipeline: `Stream Deck → Streamer.bot → Timer App → .txt file → OBS`

This is a pragmatic, battle-tested architecture. No browser sources, no fragile overlay connections. One-button operation during a live stream.

Some visual customization matters too — the timer should look good on stream — but the integration pipeline is the primary differentiator.

## Key Takeaways
- The "cool" is in the seamless triggering, not the timer display itself
- One-button Stream Deck operation during live streams is the UX goal
- Text file transport is deliberately chosen over browser sources for reliability
