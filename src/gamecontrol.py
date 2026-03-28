#!/usr/bin/env python3
"""
ITBcontrol Game Controller
Keyboard and mouse control for Into the Breach via xdotool.
Designed to be used by hermes agent or the ITBcontrol agent.

Usage as module:
    from gamecontrol import GameController
    gc = GameController()
    gc.click(400, 300)
    gc.key("Escape")
    gc.screenshot("/tmp/itb.png")

Usage as CLI:
    python3 gamecontrol.py click 400 300
    python3 gamecontrol.py key Escape
    python3 gamecontrol.py type "hello"
    python3 gamecontrol.py screenshot /tmp/itb.png
    python3 gamecontrol.py find-window
    python3 gamecontrol.py focus
"""

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

XDOTOOL = "/home/linuxbrew/.linuxbrew/bin/xdotool"
DISPLAY = os.environ.get("DISPLAY", ":0")
XAUTHORITY = os.environ.get("XAUTHORITY", "")
GAME_TITLE = "Into the Breach"


class GameController:
    """Control Into the Breach window via xdotool."""

    def __init__(self, display: str = DISPLAY, xauthority: str = ""):
        self.display = display
        self.xauthority = xauthority or self._find_xauthority()
        self.window_id: Optional[int] = None
        self.window_x = 0
        self.window_y = 0
        self.window_w = 0
        self.window_h = 0

    def _find_xauthority(self) -> str:
        """Auto-detect Xwayland auth cookie."""
        import glob
        candidates = glob.glob("/run/user/1000/.mutter-Xwaylandauth.*")
        if candidates:
            return candidates[0]
        return ""

    def _env(self) -> dict:
        env = os.environ.copy()
        env["DISPLAY"] = self.display
        if self.xauthority:
            env["XAUTHORITY"] = self.xauthority
        return env

    def _run(self, args: list, timeout: int = 10) -> str:
        """Run xdotool with proper env."""
        cmd = [XDOTOOL] + [str(a) for a in args]
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            env=self._env(), timeout=timeout
        )
        if result.returncode != 0 and result.stderr:
            raise RuntimeError(f"xdotool error: {result.stderr.strip()}")
        return result.stdout.strip()

    def find_window(self) -> Optional[int]:
        """Find the Into the Breach window ID."""
        try:
            output = self._run(["search", "--name", GAME_TITLE])
            if output:
                # Take the first window ID
                wid = int(output.strip().split("\n")[0])
                self.window_id = wid
                self._update_geometry()
                return wid
        except Exception as e:
            print(f"[gamecontrol] find_window error: {e}", file=sys.stderr)
        return None

    def _update_geometry(self):
        """Fetch window position and size."""
        if not self.window_id:
            return
        try:
            out = self._run(["getwindowgeometry", str(self.window_id)])
            for line in out.split("\n"):
                line = line.strip()
                if line.startswith("Position:"):
                    # Position: 1255,40 (screen: 0)
                    pos = line.split(":")[1].strip().split("(")[0].strip()
                    x, y = pos.split(",")
                    self.window_x = int(x)
                    self.window_y = int(y)
                elif line.startswith("Geometry:"):
                    # Geometry: 1330x813
                    geo = line.split(":")[1].strip()
                    w, h = geo.split("x")
                    self.window_w = int(w)
                    self.window_h = int(h)
        except Exception as e:
            print(f"[gamecontrol] geometry error: {e}", file=sys.stderr)

    def focus(self) -> bool:
        """Bring the game window to focus."""
        if not self.window_id:
            self.find_window()
        if not self.window_id:
            return False
        try:
            self._run(["windowactivate", "--sync", str(self.window_id)])
            time.sleep(0.2)
            return True
        except Exception:
            return False

    def click(self, x: int, y: int, button: int = 1):
        """Click at position relative to game window.

        Args:
            x: X coordinate relative to game window top-left
            y: Y coordinate relative to game window top-left
            button: 1=left, 2=middle, 3=right
        """
        if not self.window_id:
            self.find_window()
        self.focus()
        abs_x = self.window_x + x
        abs_y = self.window_y + y
        self._run(["mousemove", str(abs_x), str(abs_y)])
        time.sleep(0.05)
        self._run(["click", str(button)])

    def click_abs(self, x: int, y: int, button: int = 1):
        """Click at absolute screen position."""
        self.focus()
        self._run(["mousemove", str(x), str(y)])
        time.sleep(0.05)
        self._run(["click", str(button)])

    def double_click(self, x: int, y: int, button: int = 1):
        """Double-click at position relative to game window."""
        if not self.window_id:
            self.find_window()
        self.focus()
        abs_x = self.window_x + x
        abs_y = self.window_y + y
        self._run(["mousemove", str(abs_x), str(abs_y)])
        time.sleep(0.05)
        self._run(["click", "--repeat", "2", "--delay", "100", str(button)])

    def move_mouse(self, x: int, y: int):
        """Move mouse to position relative to game window (no click)."""
        if not self.window_id:
            self.find_window()
        abs_x = self.window_x + x
        abs_y = self.window_y + y
        self._run(["mousemove", str(abs_x), str(abs_y)])

    def key(self, key: str):
        """Press a key. Examples: Escape, Return, space, a, F1, ctrl+z"""
        self.focus()
        self._run(["key", key])

    def key_down(self, key: str):
        """Hold a key down."""
        self.focus()
        self._run(["keydown", key])

    def key_up(self, key: str):
        """Release a key."""
        self._run(["keyup", key])

    def type_text(self, text: str, delay_ms: int = 50):
        """Type a string of text."""
        self.focus()
        self._run(["type", "--delay", str(delay_ms), text])

    def drag(self, x1: int, y1: int, x2: int, y2: int, button: int = 1):
        """Drag from (x1,y1) to (x2,y2) relative to game window."""
        if not self.window_id:
            self.find_window()
        self.focus()
        ax1 = self.window_x + x1
        ay1 = self.window_y + y1
        ax2 = self.window_x + x2
        ay2 = self.window_y + y2
        self._run(["mousemove", str(ax1), str(ay1)])
        time.sleep(0.05)
        self._run(["mousedown", str(button)])
        time.sleep(0.1)
        self._run(["mousemove", "--delay", "10", str(ax2), str(ay2)])
        time.sleep(0.05)
        self._run(["mouseup", str(button)])

    def screenshot(self, output_path: str = "/tmp/itb_screen.png") -> str:
        """Take a screenshot via GNOME dbus portal (handles OpenGL windows).

        Triggers GNOME screenshot, waits for the file to appear in
        ~/Pictures/Screenshots/, then copies it to output_path.
        Falls back to ffmpeg x11grab if dbus fails.

        Returns the path to the screenshot.
        """
        screenshots_dir = Path.home() / "Pictures" / "Screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        # Record existing screenshots
        before = set(screenshots_dir.glob("*.png"))

        # Try GNOME Screenshot dbus call
        env = self._env()
        env["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=/run/user/1000/bus"
        env["XDG_RUNTIME_DIR"] = "/run/user/1000"

        try:
            subprocess.run([
                "gdbus", "call", "--session",
                "--dest", "org.gnome.Shell",
                "--object-path", "/org/gnome/Shell",
                "--method", "org.gnome.Shell.Eval",
                "global.display.get_monitor_geometry(0).width > 0 && "
                "imports.gi.Shell.Screenshot.new().screenshot(true, '/tmp/itb_screen.png', null)",
            ], capture_output=True, env=env, timeout=5)
        except Exception:
            pass

        # Wait for new file
        deadline = time.time() + 3
        new_file = None
        while time.time() < deadline:
            after = set(screenshots_dir.glob("*.png"))
            diff = after - before
            if diff:
                new_file = max(diff, key=lambda f: f.stat().st_mtime)
                break
            # Also check /tmp directly
            if Path("/tmp/itb_screen.png").exists():
                mtime = Path("/tmp/itb_screen.png").stat().st_mtime
                if mtime > time.time() - 5:
                    import shutil
                    shutil.copy2("/tmp/itb_screen.png", output_path)
                    return output_path
            time.sleep(0.5)

        if new_file:
            import shutil
            shutil.copy2(new_file, output_path)
            return output_path

        # Fallback: ffmpeg x11grab (may show black for OpenGL windows)
        if not self.window_id:
            self.find_window()
        self._update_geometry()
        cmd = [
            "ffmpeg", "-y",
            "-f", "x11grab",
            "-s", f"{self.window_w}x{self.window_h}",
            "-i", f"{self.display}+{self.window_x},{self.window_y}",
            "-vframes", "1",
            output_path,
        ]
        subprocess.run(cmd, capture_output=True, env=self._env(), timeout=10)
        return output_path

    def info(self) -> dict:
        """Return current window info."""
        if not self.window_id:
            self.find_window()
        self._update_geometry()
        return {
            "window_id": self.window_id,
            "x": self.window_x,
            "y": self.window_y,
            "width": self.window_w,
            "height": self.window_h,
            "display": self.display,
            "xauthority": self.xauthority,
        }

    def wait_for_window(self, timeout: int = 60) -> bool:
        """Wait for the game window to appear."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.find_window():
                return True
            time.sleep(2)
        return False


# ── CLI interface ───────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    gc = GameController()
    cmd = sys.argv[1]

    if cmd == "find-window":
        wid = gc.find_window()
        if wid:
            print(f"Window ID: {wid}")
            print(f"Position:  {gc.window_x},{gc.window_y}")
            print(f"Size:      {gc.window_w}x{gc.window_h}")
        else:
            print("Game window not found")
            sys.exit(1)

    elif cmd == "focus":
        if gc.focus():
            print("Focused")
        else:
            print("Failed to focus")
            sys.exit(1)

    elif cmd == "click":
        x, y = int(sys.argv[2]), int(sys.argv[3])
        button = int(sys.argv[4]) if len(sys.argv) > 4 else 1
        gc.click(x, y, button)
        print(f"Clicked ({x}, {y}) button={button}")

    elif cmd == "key":
        key = sys.argv[2]
        gc.key(key)
        print(f"Key: {key}")

    elif cmd == "type":
        text = sys.argv[2]
        gc.type_text(text)
        print(f"Typed: {text}")

    elif cmd == "screenshot":
        path = sys.argv[2] if len(sys.argv) > 2 else "/tmp/itb_screen.png"
        gc.screenshot(path)
        print(f"Screenshot saved: {path}")

    elif cmd == "info":
        import json
        print(json.dumps(gc.info(), indent=2))

    elif cmd == "drag":
        x1, y1, x2, y2 = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
        gc.drag(x1, y1, x2, y2)
        print(f"Dragged ({x1},{y1}) -> ({x2},{y2})")

    elif cmd == "move":
        x, y = int(sys.argv[2]), int(sys.argv[3])
        gc.move_mouse(x, y)
        print(f"Moved to ({x}, {y})")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
