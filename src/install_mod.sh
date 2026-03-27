#!/bin/bash
# Install the ITBcontrol mod into the game directory
# Run this once before launching the game.

GAME_DIR="${1:-/home/iroko/Games/Heroic/IntoTheBreach}"
MOD_DIR="$(dirname "$0")/../mod"

echo "[install] Game dir: $GAME_DIR"
echo "[install] Mod dir:  $MOD_DIR"

# Create user/ folder if it doesn't exist
mkdir -p "$GAME_DIR/user"

# Copy mod files
cp "$MOD_DIR/missionData.lua" "$GAME_DIR/user/missionData.lua"
cp "$MOD_DIR/itbcontrol.lua"  "$GAME_DIR/user/itbcontrol.lua"

echo "[install] Installed:"
ls -la "$GAME_DIR/user/"
echo ""
echo "[install] Done. Launch the game via Heroic, then run:"
echo "  python3 src/agent.py --game-dir '$GAME_DIR' --api-key YOUR_KEY"
