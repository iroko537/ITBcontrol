# ITBcontrol Architecture

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Into the Breach (Breach.exe via Wine/Heroic)                │
│                                                             │
│  Lua mod (user/itbcontrol.lua)                             │
│    ├── hooks Mission:UpdateMission() each game turn        │
│    ├── dumps board state → itbcontrol_state.json           │
│    └── reads itbcontrol_action.json → executes move        │
└─────────────────┬────────────────────────────┬─────────────┘
                  │ state.json                  │ action.json
                  ▼                             ▲
┌─────────────────────────────────────────────────────────────┐
│  Python Agent (src/agent.py)                                │
│                                                             │
│    poll loop                                                │
│      ├── read state.json                                    │
│      ├── render board as text                               │
│      ├── call Claude API → JSON action                      │
│      ├── write action.json                                  │
│      └── (optional) xdotool click End Turn button          │
└─────────────────────────────────────────────────────────────┘
```

## File Paths

All files relative to the game working directory:
  `/home/iroko/Games/Heroic/IntoTheBreach/`

| File                       | Written by | Read by |
|----------------------------|-----------|---------|
| user/missionData.lua       | you       | game    |
| user/itbcontrol.lua        | you       | game    |
| itbcontrol_state.json      | lua mod   | agent   |
| itbcontrol_action.json     | agent     | lua mod |
| itbcontrol.log             | lua mod   | debug   |
| itbcontrol_error.log       | lua mod   | debug   |

## Lua Mod Details

- Entry: `user/missionData.lua` (loaded by `scripts/scripts.lua`)
- Main:  `user/itbcontrol.lua`
- Hooks `Mission:UpdateMission()` — called each turn by every mission type
- Also hooks `Mission:BaseStart()` to init on mission start
- Uses Lua 5.1 `io.open` for file I/O (confirmed available via GetWorkingDir)
- Uses `Board:GetPawns()`, `Board:GetTerrain()`, etc. (native C++ bindings)

## State JSON Schema

```json
{
  "turn": 3,
  "island": 1,
  "sector": 2,
  "board_w": 8,
  "board_h": 8,
  "power_grid": 7,
  "tiles": [
    {"x":0,"y":0,"terrain":0,"is_wall":false,"is_building":false,
     "is_fire":false,"is_water":false,"is_hole":false,"is_acid":false,
     "is_smoke":false,"is_danger":false,"is_pawn":false,"pawn_team":0}
  ],
  "pawns": [
    {"id":1,"type":"PunchMech","team":2,"x":3,"y":2,
     "health":3,"max_hp":3,"move":3,"is_dead":false,
     "is_flying":false,"shields":0}
  ],
  "buildings": [
    {"x":4,"y":5,"damaged":false}
  ]
}
```

## Action JSON Schema

```json
{"type": "move",   "from": [3, 2], "to": [4, 3]}
{"type": "attack", "pawn_id": 1, "skill": 0, "target": [5, 3]}
{"type": "end_turn"}
{"type": "wait"}
```

## Team Constants (Lua)

| Constant    | Value | Meaning         |
|-------------|-------|-----------------|
| TEAM_NONE   | 0     | No team / empty |
| TEAM_PLAYER | 1     | Player units    |
| TEAM_MECH   | 2     | Mechs           |
| TEAM_ENEMY  | 3     | Vek enemies     |

## Setup

1. Install mod:  `bash src/install_mod.sh`
2. Launch game via Heroic (starts Breach.exe via Wine)
3. Start agent: `python3 src/agent.py --api-key $KEY`

## Known Limitations

- Skill/attack execution via Lua SkillEffect needs more testing
- End Turn requires xdotool UI click (xdotool must be installed)
- Agent reads turn change by polling state.json — no push notification
- GetHealth/GetMaxHealth require checking IsAbility() first
- Community ITB Mod Loader not used (not installed); using raw user/ injection
