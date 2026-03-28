#!/usr/bin/env python3
"""ITB Control — Web UI server for Into the Breach battlefield viewer/controller."""

import argparse
import json
import os
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

DEFAULT_PORT = 8080
DEFAULT_GAME_DIR = "/home/iroko/Games/Heroic/IntoTheBreach"

app = Flask(__name__, static_folder=None)
GAME_DIR: Path = Path(DEFAULT_GAME_DIR)


# ── Static files ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(
        os.path.join(os.path.dirname(__file__), "static"), "index.html"
    )


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(
        os.path.join(os.path.dirname(__file__), "static"), filename
    )


# ── API ───────────────────────────────────────────────────────────────────────

@app.route("/api/state")
def api_state():
    state_file = GAME_DIR / "itbcontrol_state.json"
    if not state_file.exists():
        return jsonify({"error": "no state file", "path": str(state_file)}), 200
    try:
        data = json.loads(state_file.read_text())
        data["_ts"] = os.path.getmtime(state_file)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/action", methods=["POST"])
def api_action():
    action = request.get_json(force=True)
    if not action:
        return jsonify({"error": "empty body"}), 400
    action_file = GAME_DIR / "itbcontrol_action.json"
    action_file.write_text(json.dumps(action, indent=2))
    return jsonify({"ok": True, "action": action})


# ── CORS ──────────────────────────────────────────────────────────────────────

@app.after_request
def cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global GAME_DIR
    parser = argparse.ArgumentParser(description="ITB Control Web UI")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--game-dir", type=str, default=DEFAULT_GAME_DIR)
    args = parser.parse_args()
    GAME_DIR = Path(args.game_dir)
    print(f"[ITBControl] Serving on http://localhost:{args.port}")
    print(f"[ITBControl] Game dir: {GAME_DIR}")
    print(f"[ITBControl] State file: {GAME_DIR / 'itbcontrol_state.json'}")
    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()
