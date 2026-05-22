#!/usr/bin/env python3
"""
atv-wrapper — HTTP-Wrapper für atv-dg CLI.

Wird als systemd-User-Service auf claude-code-server gestartet und stellt
einen kleinen REST-Endpunkt zur Verfügung, damit Home Assistant (Bonn UND
Esslingen) den Apple TV "DG Wohnzimmer Esslingen" steuern kann, ohne SSH
oder mounten von /home/pol/.local/bin in den HA-Docker-Container.

Listening: 0.0.0.0:9876  — Tailscale-Interface 100.109.100.33 ist reachable;
LAN/Public reicht der systemd-Firewall-Default nicht durch, aber wir
verlangen zusätzlich Bearer-Auth.

Endpoints (alle erfordern Header `Authorization: Bearer <token>` außer /healthz):

  GET  /healthz                       — alive-check
  GET  /atv/dg/state                  — JSON: { app, app_id, playing_state, title, volume, position, total }
  POST /atv/dg/launch_app             body { bundle_id: "com.netflix.Netflix" }
  POST /atv/dg/key                    body { key: "home|menu|select|up|down|left|right|play_pause|play|pause|stop|volume_up|volume_down|screensaver" }
  POST /atv/dg/volume                 body { level: 0.5 }   # 0-1 → 0-100 für atvremote
  POST /atv/dg/audio_output           body { devices: ["DG HomePod Mini", ...] }   # via airplay_output_devices

Auth-Token: ~/Claude/credentials/AppleTV/wrapper-token.json key "token".
"""
from __future__ import annotations

import json
import os
import subprocess
import shlex
from pathlib import Path
from flask import Flask, request, jsonify

CREDS = Path.home() / "Claude/credentials/AppleTV/wrapper-token.json"
ATV_DG = str(Path.home() / ".local/bin/atv-dg")

ALLOWED_KEYS = {
    "home", "menu", "select", "up", "down", "left", "right",
    "play_pause", "play", "pause", "stop",
    "volume_up", "volume_down",
    "screensaver", "top_menu", "next", "previous",
    "skip_forward", "skip_backward", "channel_up", "channel_down",
    "suspend", "turn_on", "turn_off",
}

with open(CREDS) as f:
    TOKEN = json.load(f)["token"]

app = Flask(__name__)


def _auth_ok(req) -> bool:
    h = req.headers.get("Authorization", "")
    return h == f"Bearer {TOKEN}"


def _run_atv(args: list[str], timeout: int = 25) -> dict:
    """Run atv-dg with given args, return {ok, stdout, stderr, returncode}."""
    cmd = [ATV_DG, *args]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "cmd": " ".join(shlex.quote(c) for c in cmd),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": -1, "stdout": "", "stderr": "timeout", "cmd": " ".join(cmd)}
    except Exception as e:
        return {"ok": False, "returncode": -1, "stdout": "", "stderr": f"exception: {e}", "cmd": " ".join(cmd)}


def _require_auth():
    if not _auth_ok(request):
        return jsonify({"error": "unauthorized"}), 401
    return None


@app.route("/healthz", methods=["GET"])
def healthz():
    # cheap smoke-check that atv-dg binary exists; no Apple-TV call
    exists = os.path.exists(ATV_DG)
    return jsonify({"ok": exists, "service": "atv-wrapper", "atv_dg": ATV_DG})


_STATE_CACHE = {"ts": 0.0, "data": {}}
_STATE_TTL = 25.0  # seconds


@app.route("/atv/dg/state", methods=["GET"])
def state():
    err = _require_auth()
    if err: return err
    import time
    from concurrent.futures import ThreadPoolExecutor
    now = time.time()
    if (now - _STATE_CACHE["ts"]) < _STATE_TTL and _STATE_CACHE["data"]:
        return jsonify(_STATE_CACHE["data"])
    # Run the three pyatv calls in parallel — each ~4s with the tvOS-26-stall
    with ThreadPoolExecutor(max_workers=3) as ex:
        fut_app = ex.submit(_run_atv, ["app"])
        fut_playing = ex.submit(_run_atv, ["playing"])
        fut_vol = ex.submit(_run_atv, ["volume"])
        app_res = fut_app.result()
        playing_res = fut_playing.result()
        vol_res = fut_vol.result()
    state = {
        "app_raw": app_res.get("stdout", ""),
        "playing_raw": playing_res.get("stdout", ""),
        "volume_raw": vol_res.get("stdout", ""),
    }
    # naive parsing
    if app_res["ok"] and "App: " in app_res["stdout"]:
        line = [l for l in app_res["stdout"].splitlines() if l.startswith("App: ")]
        if line:
            txt = line[0][len("App: "):]
            if " (" in txt and txt.endswith(")"):
                name, bid = txt.rsplit(" (", 1)
                state["app"] = name
                state["app_id"] = bid[:-1]
            else:
                state["app"] = txt
    if playing_res["ok"]:
        for ln in playing_res["stdout"].splitlines():
            if "Device state:" in ln:
                state["playing_state"] = ln.split(":", 1)[1].strip()
            elif "Title:" in ln:
                state["title"] = ln.split(":", 1)[1].strip()
            elif "Position:" in ln:
                state["position"] = ln.split(":", 1)[1].strip()
            elif "Media type:" in ln:
                state["media_type"] = ln.split(":", 1)[1].strip()
    if vol_res["ok"]:
        try:
            state["volume"] = float(vol_res["stdout"].splitlines()[-1])
        except Exception:
            pass
    _STATE_CACHE["ts"] = now
    _STATE_CACHE["data"] = state
    return jsonify(state)


@app.route("/atv/dg/launch_app", methods=["POST"])
def launch_app():
    err = _require_auth()
    if err: return err
    body = request.get_json(force=True, silent=True) or {}
    bundle_id = body.get("bundle_id", "").strip()
    if not bundle_id or not all(c.isalnum() or c in ".-_" for c in bundle_id):
        return jsonify({"error": "invalid bundle_id"}), 400
    res = _run_atv([f"launch_app={bundle_id}"])
    return jsonify(res), (200 if res["ok"] else 502)


@app.route("/atv/dg/key", methods=["POST"])
def key():
    err = _require_auth()
    if err: return err
    body = request.get_json(force=True, silent=True) or {}
    k = body.get("key", "").strip()
    if k not in ALLOWED_KEYS:
        return jsonify({"error": "invalid key", "allowed": sorted(ALLOWED_KEYS)}), 400
    res = _run_atv([k])
    return jsonify(res), (200 if res["ok"] else 502)


@app.route("/atv/dg/volume", methods=["POST"])
def volume():
    err = _require_auth()
    if err: return err
    body = request.get_json(force=True, silent=True) or {}
    try:
        level = float(body.get("level"))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid level (need float 0-1)"}), 400
    if not (0.0 <= level <= 1.0):
        return jsonify({"error": "level out of range 0-1"}), 400
    # atvremote set_volume erwartet 0-100
    res = _run_atv([f"set_volume={level * 100:.0f}"])
    return jsonify(res), (200 if res["ok"] else 502)


@app.route("/atv/dg/audio_output", methods=["POST"])
def audio_output():
    err = _require_auth()
    if err: return err
    body = request.get_json(force=True, silent=True) or {}
    devices = body.get("devices") or []
    if not isinstance(devices, list) or not all(isinstance(d, str) for d in devices):
        return jsonify({"error": "devices must be list of strings"}), 400
    # pyatv: set_output_devices=<id1>,<id2>  – braucht MAC-IDs;
    # für Namen-basiert: separat erst output_devices auflisten lassen.
    # Hier: einfache Variante über raop-target; falls Name angegeben, just relay.
    arg = "set_output_devices=" + ",".join(devices)
    res = _run_atv([arg])
    return jsonify(res), (200 if res["ok"] else 502)


if __name__ == "__main__":
    # Listen auf 0.0.0.0 damit Tailscale 100.x reachable ist;
    # Bearer-Auth schützt vor unauthorisierten Zugriffen.
    app.run(host="0.0.0.0", port=9876, debug=False)
