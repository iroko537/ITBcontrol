#!/usr/bin/env python3
"""
ITBcontrol Agent
Reads board state from the game's Lua mod, calls Claude for a decision,
writes the action back, and optionally simulates UI input via xdotool.

Usage:
    python3 agent.py [--game-dir PATH] [--model MODEL] [--dry-run]

Defaults:
    --game-dir  /home/iroko/Games/Heroic/IntoTheBreach
    --model     claude-haiku-4-5  (fast, cheap)
    --dry-run   just print decisions, don't write actions
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from logger import ITBLogger

# ── Config ──────────────────────────────────────────────────────────────────

DEFAULT_GAME_DIR = Path("/home/iroko/Games/Heroic/IntoTheBreach")
STATE_FILE  = "itbcontrol_state.json"
ACTION_FILE = "itbcontrol_action.json"
POLL_INTERVAL = 0.5   # seconds between state file checks
STATE_TIMEOUT = 120   # seconds to wait for a new state

# ── State reader ─────────────────────────────────────────────────────────────

def read_state(game_dir: Path) -> Optional[dict]:
    path = game_dir / STATE_FILE
    try:
        return json.loads(path.read_text())
    except Exception:
        return None

def write_action(game_dir: Path, action: dict):
    path = game_dir / ACTION_FILE
    path.write_text(json.dumps(action))
    print(f"[agent] Action written: {action}")

def delete_state(game_dir: Path):
    path = game_dir / STATE_FILE
    try:
        path.unlink()
    except FileNotFoundError:
        pass

# ── Board renderer (text) ─────────────────────────────────────────────────

TERRAIN_NAMES = {
    0: ".", 1: "W", 2: "~", 3: "#", 4: "^",
}

def render_board(state: dict) -> str:
    w = state.get("board_w", 8)
    h = state.get("board_h", 8)

    # Build grid
    grid = [["." for _ in range(w)] for _ in range(h)]

    for t in state.get("tiles", []):
        x, y = t["x"], t["y"]
        if t.get("is_wall"):      grid[y][x] = "#"
        elif t.get("is_building"):grid[y][x] = "B"
        elif t.get("is_fire"):    grid[y][x] = "f"
        elif t.get("is_water"):   grid[y][x] = "~"
        elif t.get("is_hole"):    grid[y][x] = "O"
        elif t.get("is_acid"):    grid[y][x] = "a"
        elif t.get("is_smoke"):   grid[y][x] = "s"
        elif t.get("is_danger"):  grid[y][x] = "!"

    for p in state.get("pawns", []):
        x, y = p["x"], p["y"]
        team = p.get("team", 0)
        if team == 2:   grid[y][x] = "M"   # mech / player mech
        elif team == 1: grid[y][x] = "P"   # player
        elif team == 3: grid[y][x] = "E"   # enemy
        else:           grid[y][x] = "?"

    lines = []
    lines.append(f"  " + "".join(str(i) for i in range(w)))
    for y in range(h - 1, -1, -1):   # ITB: y=0 at bottom
        lines.append(f"{y} " + "".join(grid[y]))
    return "\n".join(lines)

def describe_pawns(state: dict) -> str:
    lines = []
    for p in state.get("pawns", []):
        team_name = {1: "Player", 2: "Mech", 3: "Enemy"}.get(p["team"], "Unknown")
        hp = f"hp={p['health']}/{p['max_hp']}" if p['health'] >= 0 else ""
        shields = f" shields={p['shields']}" if p['shields'] else ""
        danger = " (DEAD)" if p['is_dead'] else ""
        lines.append(
            f"  [{team_name}] id={p['id']} type={p['type']} "
            f"pos=({p['x']},{p['y']}) {hp}{shields} move={p['move']}{danger}"
        )
    for b in state.get("buildings", []):
        dmg = " DAMAGED" if b.get("damaged") else ""
        lines.append(f"  [Building] pos=({b['x']},{b['y']}){dmg}")
    return "\n".join(lines) if lines else "  (none)"

# ── LLM Decision ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an AI playing Into the Breach, a turn-based tactics game.

GAME RULES:
- 8x8 grid. You control Mechs (M/P). Enemies (E) attack buildings (B) each turn.
- Your goal: protect buildings from enemy attacks, defeat enemies.
- Each mech can MOVE once, then USE one skill (attack/ability), then END TURN.
- You see the board where:
  M/P = your mechs, E = enemies, B = buildings
  # = wall, ~ = water, O = hole, f = fire, ! = danger tile

DECISION FORMAT:
You must output a JSON action. Choose one of:
  {"type": "move",   "from": [x, y], "to": [x, y]}
  {"type": "attack", "pawn_id": ID, "skill": 0, "target": [x, y]}
  {"type": "end_turn"}
  {"type": "wait"}

Think step by step:
1. Identify threats: which enemies will attack which buildings?
2. Identify opportunities: can you block, push, or kill enemies?
3. Choose the highest-value action.

Output ONLY the JSON action, no explanation."""

def get_llm_action(state: dict, client, model: str, logger: "ITBLogger" = None) -> dict:
    board_str = render_board(state)
    pawn_str  = describe_pawns(state)
    power     = state.get("power_grid", "?")
    turn      = state.get("turn", "?")

    prompt = f"""Turn {turn} | Power Grid: {power}

BOARD (M=your mech, P=player, E=enemy, B=building, #=wall, ~=water, O=hole, f=fire, !=danger):
{board_str}

UNITS:
{pawn_str}

What is your action?"""

    inputs = {"model": model, "turn": state.get("turn"), "prompt_len": len(prompt)}
    try:
        response = client.messages.create(
            model=model,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        print(f"[agent] LLM response: {raw}")
        # extract JSON
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start >= 0 and end > start:
            action = json.loads(raw[start:end])
            if logger:
                logger.log_tool_call("llm_call", inputs, result=action)
                logger.log_event("llm_decision", {
                    "action_type": action.get("type"),
                    "from": action.get("from"),
                    "to":   action.get("to"),
                    "raw":  raw[:200],
                })
            return action
    except Exception as e:
        print(f"[agent] LLM error: {e}")
        if logger:
            logger.log_tool_call("llm_call", inputs, error=e)

    return {"type": "wait"}

# ── xdotool UI control ────────────────────────────────────────────────────

def find_game_window() -> Optional[int]:
    try:
        out = subprocess.check_output(
            ["xdotool", "search", "--name", "Into the Breach"],
            text=True
        ).strip()
        if out:
            return int(out.split()[0])
    except Exception:
        pass
    return None

def click_end_turn(win_id: Optional[int]):
    """Click the End Turn button — bottom-right area of the game window."""
    if not win_id:
        print("[agent] No game window found for end turn click")
        return
    try:
        # Get window geometry
        info = subprocess.check_output(
            ["xdotool", "getwindowgeometry", str(win_id)], text=True
        )
        # Parse width/height
        geo = {}
        for line in info.splitlines():
            if "Geometry:" in line:
                parts = line.strip().split()[-1].split("x")
                geo["w"], geo["h"] = int(parts[0]), int(parts[1])
            if "Position:" in line:
                pos = line.strip().split()[-2].split(",")
                geo["x"], geo["y"] = int(pos[0].rstrip(",")), int(pos[1])

        if geo:
            # End Turn button is roughly at 85% width, 92% height
            btn_x = geo.get("x", 0) + int(geo.get("w", 1920) * 0.85)
            btn_y = geo.get("y", 0) + int(geo.get("h", 1080) * 0.92)
            subprocess.run(["xdotool", "mousemove", str(btn_x), str(btn_y)])
            time.sleep(0.2)
            subprocess.run(["xdotool", "click", "1"])
            print(f"[agent] Clicked End Turn at ({btn_x}, {btn_y})")
    except Exception as e:
        print(f"[agent] xdotool error: {e}")

# ── Main loop ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-dir", default=str(DEFAULT_GAME_DIR))
    parser.add_argument("--model",    default="claude-haiku-4-5")
    parser.add_argument("--dry-run",  action="store_true")
    args = parser.parse_args()

    game_dir = Path(args.game_dir)
    print(f"[agent] Watching {game_dir / STATE_FILE}")
    print(f"[agent] Model: {args.model}")
    print(f"[agent] Dry run: {args.dry_run}")

    # Set up LLM client via hermes' Anthropic adapter (supports OAuth tokens)
    sys.path.insert(0, "/home/iroko/.hermes/hermes-agent")
    from agent.anthropic_adapter import build_anthropic_client, resolve_anthropic_token
    token = resolve_anthropic_token()
    if not token:
        print("[agent] ERROR: No Anthropic token found. Check ~/.hermes/.env")
        sys.exit(1)
    client = build_anthropic_client(token)
    use_anthropic = True  # flag for API format

    last_turn = -1
    win_id    = None

    # Init logger
    logger = ITBLogger()

    print("[agent] Waiting for game state...")
    logger.log_event("agent_start", {"model": args.model, "game_dir": str(game_dir), "dry_run": args.dry_run})

    try:
        # Find game window and take BEFORE screenshot
        win_id = find_game_window()
        logger.log_tool_call("find_game_window", {}, result=win_id)
        logger.screenshot("before_session", win_id)

        while True:
            state = read_state(game_dir)

            if state is None:
                time.sleep(POLL_INTERVAL)
                continue

            turn = state.get("turn", -1)
            if turn == last_turn:
                time.sleep(POLL_INTERVAL)
                continue

            last_turn = turn
            print(f"\n[agent] === Turn {turn} ===")
            print(render_board(state))
            print(describe_pawns(state))

            # Log turn start
            logger.log_event("turn_start", {
                "turn":           turn,
                "pawn_count":     len(state.get("pawns", [])),
                "building_count": len(state.get("buildings", [])),
                "power_grid":     state.get("power_grid"),
                "board":          render_board(state),
            })

            # Screenshot at start of turn
            logger.screenshot(f"turn_{turn:03d}_before", win_id)

            # Get LLM decision
            action = get_llm_action(state, client, args.model, logger)
            print(f"[agent] Decision: {action}")

            if not args.dry_run:
                write_action(game_dir, action)
                logger.log_tool_call("write_action", {"path": str(game_dir / ACTION_FILE)}, result=action)
                logger.log_event("action_written", {"action": action})

                # If end_turn, also simulate UI click
                if action.get("type") == "end_turn":
                    time.sleep(0.5)
                    click_end_turn(win_id)
                    logger.log_tool_call("click_end_turn", {"win_id": win_id})

            # Screenshot after action
            time.sleep(0.8)
            logger.screenshot(f"turn_{turn:03d}_after", win_id)

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n[agent] Interrupted.")
        # Take final screenshot
        logger.screenshot("after_session", win_id)
        logger.close(outcome="interrupted")
    except Exception as e:
        logger.log_tool_call("agent_loop", {}, error=e)
        logger.screenshot("after_session_error", win_id)
        logger.close(outcome=f"error: {e}")
        raise

if __name__ == "__main__":
    main()
