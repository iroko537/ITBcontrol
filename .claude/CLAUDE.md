# ITBcontrol — Claude Code Context

## Project Goal
Control Into the Breach (ITB) with an LLM agent via a Lua mod bridge.

## Game Location
/home/iroko/Games/Heroic/IntoTheBreach/
- Breach.exe  (Windows exe, runs via Wine through Heroic launcher)
- scripts/    Lua game scripts (read-only, game source)
- scripts/modloader.lua  (empty — community modloader not installed yet)
- user/       Created at runtime by the game — mod drop folder

## Key Facts
- Epic Store version, NOT Steam. No Steam Workshop.
- Game runs via Wine/Proton managed by Heroic.
- Lua 5.1 scripting with modloader support.
- Board is 8x8, turn-based, perfect information.
- Wiki archive at /home/iroko/agents/hermes/openITB (530 pages, MediaWiki JSON).

## Architecture
1. Lua mod (mod/) dumps board state to a JSON file each turn.
2. Python agent (src/) reads state, calls LLM, writes action JSON.
3. Lua mod polls action JSON and executes the move.

## Folder Layout
- mod/     Lua mod code
- src/     Python agent
- docs/    Design notes
- sessions/ Local session transcripts

## Current Status
Exploring modloader API. scripts/modloader.lua is empty.
Need to determine if community modloader is needed or if we can inject
directly via user/ folder scripts.
