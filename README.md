# ITBcontrol

LLM agent controller for Into the Breach.

## Goal

Control Into the Breach via a Lua mod that exposes game state as structured JSON,
paired with a Python agent that reads state, calls an LLM for decisions, and writes
actions back into the game.

## Architecture

```
Game (Breach.exe via Wine/Heroic)
  └── Lua mod (mod/)
        ├── dumps board state -> state.json each turn
        └── reads action.json -> executes move/attack

Python agent (src/)
  ├── reads state.json
  ├── calls LLM (Claude) with board context
  ├── writes action.json
  └── loop
```

## Folder Structure

- mod/       Lua mod for ITB (state export + action polling)
- src/       Python agent (LLM loop, state parser, action writer)
- docs/      Design notes, game API reference, session notes
- sessions/  Local session transcripts for this project
- .claude/   Claude Code config and context files

## Game Location

/home/iroko/Games/Heroic/IntoTheBreach/Breach.exe (Epic, via Heroic/Wine)

## Status

Early exploration — investigating modloader API and game state structure.
