# Approaches

> Office Hours — Builder Mode
> Date: 2026-04-04
> Phase: Alternatives Generation

## Context
Three product approaches evaluated based on diagnostic findings, landscape analysis, and validated premises.

## Approaches

### APPROACH A: Skateboard First
**Summary:** Python CLI that takes a duration, counts down, writes to a text file. No GUI, no integrations. Usable on stream within an hour of starting.
**Effort:** S
**Risk:** Low
**Pros:**
- Usable immediately
- Forces validation of the text-file-to-OBS pipeline before adding complexity
- Can wire to Streamer.bot as an external command right away
**Cons:**
- No GUI means manual command entry or Streamer.bot action setup
- Single timer only
- Not shareable with non-technical streamers

### APPROACH B: GUI App with Streamer.bot Pipeline
**Summary:** Jump straight to the Bicycle tier — lightweight GUI with preset buttons, text file output, and Streamer.bot WebSocket listener so Stream Deck triggers work from day one.
**Effort:** M
**Risk:** Med
**Pros:**
- The full pipeline works end-to-end from the start
- GUI makes it usable and demo-able to other streamers
- Multiple timer support baked in from the architecture
**Cons:**
- More upfront work before first use on stream
- WebSocket integration adds debugging surface area
- Risk of scope creep into Car features before Bicycle is solid

### APPROACH C: OBS-Native + External Trigger Hybrid
**Summary:** Build the timer display as an OBS Lua script (native, no text files needed) but expose a local HTTP/WebSocket API that Streamer.bot can hit. Best of both worlds — native OBS rendering with external control.
**Effort:** M
**Risk:** Med-High
**Pros:**
- No text file polling — timer updates are instant in OBS
- Lua scripts are lightweight and portable
- Other streamers can install it as an OBS plugin
**Cons:**
- Lua scripting in OBS is poorly documented and finicky
- Splits the codebase across two languages (Python + Lua)
- Harder to debug than a standalone app

## Chosen Approach

**RECOMMENDATION: Approach B (GUI App with Streamer.bot Pipeline)**

The Bicycle tier is where the product becomes interesting. The user already has a well-structured skateboard/bicycle/car spec, and the Bicycle tier delivers the core differentiator — Streamer.bot WebSocket integration with a usable GUI. The skateboard CLI can be built as a natural milestone along the way, and the Car features layer on after the pipeline is proven.

## Rationale
- The landscape gap is specifically "Streamer.bot-native timer with GUI" — Approach B fills that gap directly
- Approach A is too minimal to demo or share; Approach C introduces unnecessary complexity
- The user's existing spec already breaks Approach B into manageable pieces
