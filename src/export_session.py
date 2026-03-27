#!/usr/bin/env python3
"""Export a Hermes session JSON to a readable Markdown transcript."""
import json, sys
from pathlib import Path

sessions_dir = Path.home() / ".hermes/sessions"
out_dir = Path("/home/iroko/agents/hermes/ITBcontrol/sessions")
out_dir.mkdir(exist_ok=True)

# Sessions to export
session_ids = [
    "20260327_230837_50d503",  # main ITBcontrol session (iemo + ITB exploration)
    "20260327_231707_8a375e",  # iemo monitor session
    "20260327_231350_0bd992",  # iemo scrape_details session
    "20260327_232123_87721b",  # current session
]

for sid in session_ids:
    src = sessions_dir / f"session_{sid}.json"
    if not src.exists():
        print(f"Not found: {src}")
        continue

    data = json.loads(src.read_text())
    messages = data.get("messages", [])
    out_file = out_dir / f"session_{sid}_transcript.md"

    lines = [
        f"# Session Transcript",
        f"**Session ID:** {sid}",
        f"**Source:** TUI/cli",
        f"**Date:** 2026-03-27",
        f"",
        f"> Note: hidden chain-of-thought is not included verbatim; reasoning is summarized.",
        "",
    ]

    for msg in messages:
        role = msg.get("role", "")
        ts = msg.get("timestamp", "")
        if ts:
            ts = ts[11:19]
        content = msg.get("content", "")

        if role == "user":
            lines.append("---")
            lines.append(f"## USER [{ts}]")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        lines.append(block["text"])
            else:
                lines.append(str(content))
            lines.append("")

        elif role == "assistant":
            lines.append(f"## ASSISTANT [{ts}]")
            if isinstance(content, list):
                for block in content:
                    t = block.get("type", "") if isinstance(block, dict) else ""
                    if t == "text":
                        lines.append(block["text"])
                    elif t == "thinking":
                        summary = block.get("thinking", "")[:300].replace("\n", " ")
                        lines.append(f"> [thinking: {summary}...]")
                    elif t == "tool_use":
                        inp = json.dumps(block.get("input", {}), indent=2)
                        if len(inp) > 800:
                            inp = inp[:800] + "\n... (truncated)"
                        lines.append(f"```tool_call")
                        lines.append(f"Tool: {block.get('name')}")
                        lines.append(f"Input:\n{inp}")
                        lines.append(f"```")
            else:
                lines.append(str(content))
            lines.append("")

        elif role == "tool":
            lines.append(f"## TOOL RESULT [{ts}]")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        for c in block.get("content", []):
                            if isinstance(c, dict) and c.get("type") == "text":
                                txt = c["text"]
                                if len(txt) > 2000:
                                    txt = txt[:2000] + "\n... (truncated)"
                                lines.append("```")
                                lines.append(txt)
                                lines.append("```")
            lines.append("")

    out_file.write_text("\n".join(lines))
    print(f"Exported {sid} -> {out_file.name} ({len(messages)} messages)")

print("Done.")
