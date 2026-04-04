# Success Criteria

> Office Hours — Builder Mode
> Date: 2026-04-04
> Phase: Success Criteria

## Context
Defining what "done" looks like for the chosen approach (Approach B: GUI + Streamer.bot Pipeline), broken down by tier.

## What "Done" Looks Like

### Skateboard Milestone (embedded in Approach B)
- [ ] Python script accepts a timer duration and counts down
- [ ] Writes formatted time (MM:SS or HH:MM:SS) to a `.txt` file
- [ ] OBS GDI+ text source successfully reads and displays the countdown
- [ ] Timer reaches zero and stops (or displays a configurable end message)

### Bicycle Tier (Primary Target)
- [ ] GUI window with preset timer buttons (e.g., 5m, 10m, 15m, custom)
- [ ] Start/stop/reset controls
- [ ] Text file output that OBS reads in real time
- [ ] Streamer.bot WebSocket listener — can receive "start timer" commands
- [ ] Stream Deck button → Streamer.bot action → timer starts on stream
- [ ] Multiple timer support — at least 2 timers writing to separate files
- [ ] Runs reliably for a full stream session (3-6 hours) without crashing

### Car Tier (Future)
- [ ] Customizable timer presets saved between sessions
- [ ] Sound alerts on timer completion
- [ ] Pause/resume functionality
- [ ] Count-up mode
- [ ] Configurable output file paths
- [ ] Stream Deck support with multiple actions (start, pause, reset different timers)

### The Real Test
**You use it on your own stream for a full session and don't switch back to whatever you're using now.** If you find yourself alt-tabbing to fix it or working around it, it's not done yet.

## Key Takeaways
- The Bicycle tier is the ship target — Car features are earned after that's solid
- "Runs reliably for a full stream session" is the unglamorous but critical criterion
- Self-use is the ultimate validation — if you don't use it, nobody else will
