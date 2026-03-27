#!/usr/bin/env python3
"""
ITBcontrol Logger
Handles structured logging of tool calls, game session events,
and screenshots (before/after playing).
"""

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("/home/iroko/agents/hermes/ITBcontrol/ITBcontrol_log")

class ITBLogger:
    def __init__(self, session_id: str = None):
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = LOG_DIR / self.session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self.tool_log_path    = self.session_dir / "tool_calls.jsonl"
        self.game_log_path    = self.session_dir / "game_session.jsonl"
        self.summary_log_path = self.session_dir / "summary.md"
        self._events = []

        self._write_summary_header()
        print(f"[logger] Session: {self.session_id}")
        print(f"[logger] Logs at: {self.session_dir}")

    def _ts(self):
        return datetime.now().isoformat()

    def _write_summary_header(self):
        self.summary_log_path.write_text(
            f"# ITBcontrol Session {self.session_id}\n"
            f"Started: {self._ts()}\n\n"
            f"## Events\n"
        )

    def _append_summary(self, line: str):
        with open(self.summary_log_path, "a") as f:
            f.write(line + "\n")

    # ── Tool call logging ──────────────────────────────────────────────────

    def log_tool_call(self, tool: str, inputs: dict, result=None, error=None):
        entry = {
            "ts":     self._ts(),
            "type":   "tool_call",
            "tool":   tool,
            "inputs": inputs,
            "result": result,
            "error":  str(error) if error else None,
        }
        with open(self.tool_log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        status = "ERROR" if error else "OK"
        self._append_summary(f"- [{entry['ts'][11:19]}] TOOL {tool} [{status}]")

    # ── Game session event logging ─────────────────────────────────────────

    def log_event(self, event_type: str, data: dict = None):
        entry = {
            "ts":    self._ts(),
            "type":  event_type,
            "data":  data or {},
        }
        self._events.append(entry)
        with open(self.game_log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        # summary line
        detail = ""
        if event_type == "turn_start":
            detail = f"turn={data.get('turn')} pawns={data.get('pawn_count')} buildings={data.get('building_count')}"
        elif event_type == "llm_decision":
            detail = f"action={data.get('action_type')} from={data.get('from')} to={data.get('to')}"
        elif event_type == "action_written":
            detail = f"action={json.dumps(data.get('action', {}))}"
        elif event_type == "screenshot":
            detail = f"path={data.get('path')} label={data.get('label')}"
        else:
            detail = str(data)[:80] if data else ""
        self._append_summary(f"- [{entry['ts'][11:19]}] {event_type.upper()} {detail}")

    # ── Screenshot ────────────────────────────────────────────────────────

    def screenshot(self, label: str, win_id: int = None) -> str | None:
        """Take a screenshot and save to session dir. Returns path or None."""
        ts = datetime.now().strftime("%H%M%S")
        filename = f"{ts}_{label}.png"
        path = str(self.session_dir / filename)

        try:
            if win_id:
                # screenshot of specific window
                ret = subprocess.run(
                    ["scrot", "-u", "--window", str(win_id), path],
                    capture_output=True, text=True, timeout=5
                )
            else:
                # full screen
                ret = subprocess.run(
                    ["scrot", path],
                    capture_output=True, text=True, timeout=5
                )

            if ret.returncode == 0 and Path(path).exists():
                self.log_event("screenshot", {"path": path, "label": label, "win_id": win_id})
                print(f"[logger] Screenshot: {path}")
                return path
            else:
                # fallback: try import from ImageMagick
                ret2 = subprocess.run(
                    ["import", "-window", "root", path],
                    capture_output=True, text=True, timeout=5
                )
                if Path(path).exists():
                    self.log_event("screenshot", {"path": path, "label": label, "method": "import"})
                    return path
                self.log_tool_call("screenshot", {"label": label}, error=ret.stderr or "scrot failed")
                return None
        except Exception as e:
            self.log_tool_call("screenshot", {"label": label}, error=e)
            return None

    # ── Session close ─────────────────────────────────────────────────────

    def close(self, outcome: str = "unknown"):
        entry = {
            "ts":      self._ts(),
            "type":    "session_end",
            "outcome": outcome,
            "total_events": len(self._events),
        }
        with open(self.game_log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        self._append_summary(
            f"\n## Summary\n"
            f"- Ended: {self._ts()}\n"
            f"- Outcome: {outcome}\n"
            f"- Total events: {len(self._events)}\n"
        )
        print(f"[logger] Session closed. Outcome: {outcome}")
