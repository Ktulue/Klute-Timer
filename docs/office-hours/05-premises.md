# Premise Challenge

> Office Hours — Builder Mode
> Date: 2026-04-04
> Phase: Premise Challenge

## Context
Testing foundational assumptions before committing to an approach. Builder mode focuses on: right problem, what happens if nothing, existing partial solutions, and scope honesty.

## Premises Tested

### 1. You need a standalone Python app
**Premise:** An OBS plugin or Lua script won't cut it because you need Streamer.bot WebSocket integration and Stream Deck triggering that lives outside OBS.

**User response:** Agree

**Assessment:** Sound. OBS plugins can't listen on WebSocket. A standalone app is the right architecture for this integration pattern.

### 2. Text file output is the right transport
**Premise:** OBS GDI+ text source reading a file is more reliable than browser sources or WebSocket-based overlays for your stream setup.

**User response:** Agree

**Assessment:** Sound. Validated by the landscape — this is the pattern 50K+ My Stream Timer users rely on. Browser sources are fragile; text files are bulletproof.

### 3. Multiple simultaneous timers matter
**Premise:** You actually need more than one timer running at once (e.g., break timer + sub goal timer).

**User response:** Agree with nuance — "not sure they'd be simultaneous, but that's a great feature I didn't think about, and would be genuinely cool."

**Assessment:** The architecture should support multiple timers, but simultaneous operation isn't a day-one requirement. Don't block shipping on this.

### 4. The scope is honest
**Premise:** The Car tier (Stream Deck support, sound alerts, pause/resume, count-up, configurable paths) is something you'll actually build, not a feature list that ensures v1 never ships.

**User response:** Agree

**Assessment:** The skateboard/bicycle/car progression is well-structured. The key discipline is shipping the Bicycle tier before adding Car features.

## Key Takeaways
- All four premises hold — no fundamental misalignment
- Multiple timers: architect for it, don't require it at launch
- Scope discipline is the main risk — the Car tier is a reward for shipping Bicycle, not a prerequisite
