#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Percy-Bodo von Oheimb-Loup / Fiberopus Castor
"""appletv-dg MCP server.

Thin stdio-MCP wrapper around the `atv-dg` CLI for Apple TV
"DG Wohnzimmer Esslingen" (tvOS 26.x, paired via AirPlay + Companion + RAOP).

Exposed tools:
  - appletv_dg_launch_app(bundle_id)
  - appletv_dg_navigate(key)
  - appletv_dg_volume(action, level?)
  - appletv_dg_current_app()
  - appletv_dg_playing()
  - appletv_dg_text_input(text)
  - appletv_dg_audio_route(target)
  - appletv_dg_health()

Each tool subprocesses ~/.local/bin/atv-dg or atv-dg-audio and returns
structured JSON. No credentials live in this file — they sit in
~/Claude/credentials/AppleTV/dg-wohnzimmer.json (chmod 600).
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from functools import wraps
from pathlib import Path
from typing import Any

# stdout is reserved for the MCP JSON-RPC transport. Do NOT reassign it —
# FastMCP.run() writes the protocol to sys.stdout at runtime, so any
# reassignment (even sys.stdout = sys.stderr) sends the initialize response
# into the void and breaks the handshake. Stray prints must instead be
# silenced at their source; logging below is already pinned to sys.stderr.
from mcp.server.fastmcp import FastMCP  # noqa: E402

logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("appletv-dg-mcp")

VERSION = "0.1.0"

HOME = Path(os.path.expanduser("~"))
ATV_DG = HOME / ".local" / "bin" / "atv-dg"
ATV_DG_AUDIO = HOME / ".local" / "bin" / "atv-dg-audio"

ALLOWED_KEYS = {
    "home", "menu", "select", "up", "down", "left", "right",
    "play_pause", "play", "pause", "stop",
    "volume_up", "volume_down",
    "screensaver", "top_menu", "next", "previous",
    "skip_forward", "skip_backward", "channel_up", "channel_down",
    "suspend",
}

AUDIO_TARGETS = {
    "homepod": "homepod-on",
    "tv": "homepod-off",
    "hdmi": "homepod-off",
    "both": "both",
}

mcp = FastMCP("appletv-dg")


def handle_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Tool {func.__name__} failed", exc_info=True)
            return json.dumps({"ok": False, "error": type(e).__name__,
                               "message": str(e)}, ensure_ascii=False)
    return wrapper


def _run(cmd: list[str], timeout: int = 30) -> dict[str, Any]:
    """Run a subprocess; return {ok, stdout, stderr, returncode}."""
    if not Path(cmd[0]).exists():
        return {"ok": False, "stdout": "", "stderr": f"missing binary: {cmd[0]}",
                "returncode": -1}
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "ok": p.returncode == 0,
            "stdout": p.stdout.strip(),
            "stderr": p.stderr.strip(),
            "returncode": p.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "timeout", "returncode": -1}


@mcp.tool()
@handle_errors
def appletv_dg_launch_app(bundle_id: str) -> str:
    """Launch an app on the Apple TV by bundle id.

    Examples: com.netflix.Netflix, com.amazon.aiv.AIVApp,
    com.google.ios.youtube, de.telekom.magentatv, com.apple.TVSettings.
    """
    if not re.match(r"^[A-Za-z0-9_.-]+$", bundle_id):
        return json.dumps({"ok": False, "error": "InvalidBundleId",
                           "message": f"bundle_id contains illegal chars: {bundle_id}"})
    res = _run([str(ATV_DG), f"launch_app={bundle_id}"])
    return json.dumps({"action": "launch_app", "bundle_id": bundle_id, **res},
                      ensure_ascii=False)


@mcp.tool()
@handle_errors
def appletv_dg_navigate(key: str) -> str:
    """Send a navigation/remote key.

    Allowed keys: home, menu, select, up, down, left, right, top_menu,
    play_pause, play, pause, stop, volume_up, volume_down, screensaver,
    next, previous, skip_forward, skip_backward, channel_up, channel_down,
    suspend.
    """
    key = key.strip().lower()
    if key not in ALLOWED_KEYS:
        return json.dumps({"ok": False, "error": "InvalidKey",
                           "message": f"key '{key}' not in allowed set",
                           "allowed": sorted(ALLOWED_KEYS)})
    res = _run([str(ATV_DG), key])
    return json.dumps({"action": "navigate", "key": key, **res}, ensure_ascii=False)


@mcp.tool()
@handle_errors
def appletv_dg_volume(action: str, level: float | None = None) -> str:
    """Volume control.

    action: 'get' | 'set' | 'up' | 'down'
    level: 0-100 (only for action='set')
    """
    action = action.strip().lower()
    if action == "get":
        res = _run([str(ATV_DG), "volume"])
        vol = None
        m = re.search(r"(\d+(?:\.\d+)?)", res.get("stdout", ""))
        if m:
            try:
                vol = float(m.group(1))
            except ValueError:
                vol = None
        return json.dumps({"action": "volume_get", "volume": vol, **res},
                          ensure_ascii=False)
    if action == "up":
        res = _run([str(ATV_DG), "volume_up"])
        return json.dumps({"action": "volume_up", **res}, ensure_ascii=False)
    if action == "down":
        res = _run([str(ATV_DG), "volume_down"])
        return json.dumps({"action": "volume_down", **res}, ensure_ascii=False)
    if action == "set":
        if level is None:
            return json.dumps({"ok": False, "error": "MissingLevel",
                               "message": "level (0-100) required for action='set'"})
        if not 0 <= float(level) <= 100:
            return json.dumps({"ok": False, "error": "InvalidLevel",
                               "message": "level must be 0-100"})
        res = _run([str(ATV_DG), f"set_volume={float(level)}"])
        return json.dumps({"action": "volume_set", "level": float(level), **res},
                          ensure_ascii=False)
    return json.dumps({"ok": False, "error": "InvalidAction",
                       "message": f"action '{action}' not in get|set|up|down"})


@mcp.tool()
@handle_errors
def appletv_dg_current_app() -> str:
    """Return the currently active app on the Apple TV.

    Note: on tvOS 26.x this often returns 'Unknown' due to a pyatv/protocol
    bug (FetchAttentionState). Use `appletv_dg_playing` to detect activity.
    """
    res = _run([str(ATV_DG), "app"])
    return json.dumps({"action": "current_app", **res}, ensure_ascii=False)


@mcp.tool()
@handle_errors
def appletv_dg_playing() -> str:
    """Return playing-state (title, device_state, position, total_time, etc.)."""
    res = _run([str(ATV_DG), "playing"])
    parsed: dict[str, Any] = {}
    for line in res.get("stdout", "").splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            parsed[k.strip().lower().replace(" ", "_")] = v.strip()
    return json.dumps({"action": "playing", "parsed": parsed, **res},
                      ensure_ascii=False)


@mcp.tool()
@handle_errors
def appletv_dg_text_input(text: str) -> str:
    """Append text to the on-screen virtual keyboard (login fields, search bars).

    Uses pyatv `text_append=<text>`. Newlines/control chars are stripped.
    """
    sanitized = re.sub(r"[\r\n\t]", " ", text)
    res = _run([str(ATV_DG), f"text_append={sanitized}"])
    return json.dumps({"action": "text_input",
                       "length": len(sanitized), **res}, ensure_ascii=False)


@mcp.tool()
@handle_errors
def appletv_dg_audio_route(target: str) -> str:
    """Set audio output routing.

    target: 'homepod' (HomePod DG Wohnzimmer only)
          | 'tv' / 'hdmi' (TV HDMI speakers only)
          | 'both' (HomePod + TV multi-output).
    """
    target = target.strip().lower()
    sub = AUDIO_TARGETS.get(target)
    if sub is None:
        return json.dumps({"ok": False, "error": "InvalidTarget",
                           "message": f"target '{target}' not in homepod|tv|both",
                           "allowed": sorted(set(AUDIO_TARGETS))})
    res = _run([str(ATV_DG_AUDIO), sub])
    return json.dumps({"action": "audio_route", "target": target, **res},
                      ensure_ascii=False)


@mcp.tool()
@handle_errors
def appletv_dg_health() -> str:
    """Return the most recent heartbeat state from the local monitor log.

    Reads the latest line of
    ~/Claude/projects/Percy_Privat_Projekte/Esslingen_Fernwartung_Mutter/_monitoring/atv-dg-heartbeat-YYYY-MM-DD.jsonl
    and reports state (OK | DEGRADED | BROKEN) without waking the TV.
    """
    mon = HOME / "Claude/projects/Percy_Privat_Projekte/Esslingen_Fernwartung_Mutter/_monitoring"
    state: dict[str, Any] = {"action": "health", "binary_exists": ATV_DG.exists()}
    alert = mon / "ALERT-atv-dg-companion-broken.flag"
    state["alert_flag"] = alert.exists()
    if mon.exists():
        logs = sorted(mon.glob("atv-dg-heartbeat-*.jsonl"))
        if logs:
            try:
                last_line = logs[-1].read_text().strip().splitlines()[-1]
                state["last_heartbeat"] = json.loads(last_line)
                state["last_log_file"] = str(logs[-1])
            except Exception as e:
                state["log_parse_error"] = str(e)
        else:
            state["last_heartbeat"] = None
    else:
        state["monitor_dir_missing"] = str(mon)
    state["ok"] = (not state["alert_flag"]) and state.get("binary_exists", False)
    return json.dumps(state, ensure_ascii=False)


if __name__ == "__main__":
    logger.info(f"appletv-dg MCP server v{VERSION} starting (stdio)")
    mcp.run()
