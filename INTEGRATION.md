# INTEGRATION — Apple TV DG Esslingen für Claude Code

## MCP-Server-Registrierung

Eintrag unter `mcpServers` in `~/.claude.json`:

```json
"appletv-dg": {
  "type": "stdio",
  "command": "/home/pol/Claude/cli-tools/AppleTV_Control/mcp-server/run.sh"
}
```

Nach **Claude-Code-Neustart** sind acht Tools verfügbar:

| Tool | Args | Beispiel |
|---|---|---|
| `mcp__appletv-dg__appletv_dg_launch_app` | `bundle_id: str` | `com.netflix.Netflix` |
| `mcp__appletv-dg__appletv_dg_navigate` | `key: str` | `home`, `menu`, `select`, `up`, `down`, `left`, `right`, `play_pause`, `top_menu` ... |
| `mcp__appletv-dg__appletv_dg_volume` | `action: str, level?: float` | `action="set", level=50` |
| `mcp__appletv-dg__appletv_dg_current_app` | — | (tvOS-26 oft `Unknown`) |
| `mcp__appletv-dg__appletv_dg_playing` | — | Title, Position, Duration |
| `mcp__appletv-dg__appletv_dg_text_input` | `text: str` | Login-/Such-Feld füllen |
| `mcp__appletv-dg__appletv_dg_audio_route` | `target: str` | `homepod` / `tv` / `both` |
| `mcp__appletv-dg__appletv_dg_health` | — | letzter Heartbeat, Alert-Flag |

## Was Claude jetzt direkt kann (ohne Bash)
- Netflix/YouTube/Prime/Magenta-TV starten
- Apple-TV-Fernbedienung emulieren (Navigation + Play/Pause)
- Lautstärke setzen (0-100)
- Audio auf HomePod oder zurück auf TV routen
- Text auf der Bildschirmtastatur tippen (z.B. für Logins, Suche)
- Health-Check ohne TV zu wecken (liest nur Heartbeat-JSONL)

## Was Claude WEITERHIN über Bash macht
- `atv-dg-with-homepod ...` (Mom-Safety-Wrapper mit Auto-Pause-Check)
- `atv-dg-heartbeat` Cron-Job (systemd-Timer)
- Repairing/Patching nach pyatv-Update

## Mom-Safety
- Heartbeat-Tool ist read-only (Volume-Read), weckt den TV **nicht** aus Standby.
- Alle anderen Tools sind aktive Befehle — vor Nutzung außerhalb Schlafzeit prüfen ob TV gerade läuft via `appletv_dg_playing` (device_state ∈ {playing, paused} → User-Aktivität, NICHT unterbrechen).

## Verifikation nach Claude-Code-Restart
```
# In neuer Session
mcp__appletv-dg__appletv_dg_health()
→ {"action": "health", "binary_exists": true, "alert_flag": false, "ok": true, ...}
```

## Troubleshooting
- `missing binary: ~/.local/bin/atv-dg` → Symlinks neu anlegen (siehe README §Installation).
- `mcp__appletv-dg__*` taucht nicht auf → `jq '.mcpServers."appletv-dg"' ~/.claude.json` prüfen, dann Claude-Code wirklich neu starten (nicht nur Reload).
- pyatv-Connection-Error → `~/Claude/cli-tools/AppleTV_Control/patches/apply_tvos26_fix.sh` neu anwenden.
