# Landscape Awareness

> Office Hours — Builder Mode
> Date: 2026-04-04
> Phase: Landscape Search

## Context
Searched for existing stream timer tools, OBS countdown alternatives, and Streamer.bot timer integrations to understand the competitive landscape and validate the gap.

## Findings

### Layer 1 — Established Knowledge
The text-file-to-OBS pipeline is the proven pattern for stream timers. Multiple tools exist:

- **My Stream Timer** (mystreamtimer.apporeum.com) — 50K+ users, writes to text files, supports countdown and count-up. Desktop app with Stream Deck integration via companion plugin.
- **Ashmanix Countdown Timer** — OBS plugin, uses native text sources, multiple timers, count up/down, scene switching on zero.
- **Timer Plugin** — OBS dock-based timer with pause/resume/reset, text-only display.
- **obs-countdown** — CLI tool (Node.js) that generates countdown files for OBS.
- **The Filenal Countdown** — Simple countdown/countup that saves to text file once per second.
- **OBS Lua Advanced Timer** — Native Lua script, sets a text source as countdown/countup.

### Layer 2 — Current Discourse
- **Streamer.bot WebSocket API** is well-documented with an official TypeScript client (`@streamerbot/client`)
- Browser source timers are popular but considered fragile
- OBS Lua scripting exists but is poorly documented and finicky
- Subathon timer repos show Streamer.bot integration patterns

### Layer 3 — Our Evidence
The existing tools split into two categories:
1. **OBS-native** (plugins, Lua scripts) — great rendering but no external trigger support
2. **Standalone apps** (My Stream Timer, CLI tools) — text file output but no Streamer.bot WebSocket integration

**The gap:** No tool combines Streamer.bot WebSocket listener + Stream Deck triggering + text file output + GUI in a single purpose-built application. My Stream Timer is the closest but uses its own Stream Deck plugin rather than going through Streamer.bot, missing the broader automation pipeline streamers already have set up.

### Eureka Check
> The conventional wisdom seems sound here. Text file output is the right transport mechanism. The differentiator is the Streamer.bot WebSocket integration — most streamers already have Streamer.bot as their automation hub, so a timer that plugs directly into that ecosystem via WebSocket has a natural distribution advantage over tools that require their own integration layer.

## Key Takeaways
- Text file → OBS GDI+ is the battle-tested transport — don't reinvent this
- The real gap is Streamer.bot-native integration, not "another timer app"
- My Stream Timer (50K users) validates demand but uses a different integration approach
