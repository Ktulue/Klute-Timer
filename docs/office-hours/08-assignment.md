# Assignment

> Office Hours — Builder Mode
> Date: 2026-04-04
> Phase: Assignment

## Context
Concrete next steps before moving into implementation planning with brainstorming.

## Your Assignment

**Set up the Streamer.bot WebSocket action and verify the pipeline works manually before writing any timer code.**

Specifically:

1. **Open Streamer.bot** and enable the WebSocket server (Settings → WebSocket Server → toggle on)
2. **Create a test action** in Streamer.bot that writes "TIMER_START" to a text file when triggered
3. **Wire a Stream Deck button** to that Streamer.bot action
4. **Add the text file as an OBS GDI+ text source** and confirm it updates on screen when you press the button
5. **Note the WebSocket server address and port** — you'll need these for the timer app's connection config

This validates the full pipeline (`Stream Deck → Streamer.bot → file → OBS`) without writing a single line of Python. If any step in this chain is flaky, you want to know now — not after you've built a GUI around it.

## Why This First
The timer code is the easy part. The integration pipeline is where things break. Proving the pipeline works end-to-end with a manual test takes 15 minutes and saves you from building a beautiful app that can't talk to Streamer.bot.

## After the Assignment
Start a new session and tell brainstorming:
> "I've done office-hours validation — context is in `docs/office-hours/`"

Brainstorming will pick up the chosen approach, tech stack, and success criteria and turn them into an implementation plan.
