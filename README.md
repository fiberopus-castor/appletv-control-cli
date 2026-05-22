# AppleTV_Control — Persistente Remote-Steuerung Apple TV DG Esslingen

CLI-Wrapper für `pyatv` mit tvOS-26.x-Patch und persistenten Pairing-Credentials.

**License:** MIT — siehe `LICENSE`.
**Repo:** https://github.com/fiberopus-castor/appletv-control-cli

## Repo-Struktur
```
AppleTV_Control/
├── bin/                    # Bash/Python-Wrapper für pyatv
│   ├── atv-dg              # Haupt-Wrapper (AirPlay+Companion+RAOP)
│   ├── atv-dg-audio        # Audio-Output-Routing (AirPlay+RAOP)
│   ├── atv-dg-with-homepod # Daily-Use mit Auto-HomePod-Routing
│   └── atv-dg-heartbeat    # Read-only Heartbeat-Monitor (systemd-Timer)
├── patches/                # tvOS-26.x pyatv-Patch
├── wrapper/                # Flask-REST-Server für HA-Integration
├── mcp-server/             # stdio-MCP-Server für Claude Code
├── README.md / CHANGELOG.md / LICENSE / INTEGRATION.md
└── venv/                   # (gitignored) Python-venv mit gepatchtem pyatv
```

## Installation (Fresh-Setup)
1. Repo klonen: `git clone https://github.com/fiberopus-castor/appletv-control-cli.git ~/Claude/cli-tools/AppleTV_Control`
2. venv anlegen: `python3 -m venv venv && ./venv/bin/pip install pyatv==0.17.0 mcp flask`
3. tvOS-26-Patch: `./patches/apply_tvos26_fix.sh`
4. **Pairing** (einmalig, erzeugt Long-Term-Keys):
   ```
   ./venv/bin/atvremote -s <APPLE-TV-IP> --protocol airplay pair
   ./venv/bin/atvremote -s <APPLE-TV-IP> --protocol companion pair
   ./venv/bin/atvremote -s <APPLE-TV-IP> --protocol raop pair
   ```
5. Credentials in `~/Claude/credentials/AppleTV/dg-wohnzimmer.json` ablegen (chmod 600), Schema:
   ```json
   {
     "host_lan": "192.168.178.46",
     "identifier": "<airplay-device-id>",
     "airplay_credentials": "...",
     "companion_credentials": "...",
     "raop_credentials": "...",
     "homepod_dg_wohnzimmer_id": "<homepod-airplay-id>"
   }
   ```
6. Symlinks: `ln -sf $PWD/bin/atv-dg ~/.local/bin/atv-dg` (analog für die anderen).
7. (Optional) MCP-Server in `~/.claude.json` registrieren — siehe `INTEGRATION.md`.

## Setup-Status
- **Apple TV:** DG Wohnzimmer Esslingen, 4K (gen 2), tvOS 26.5
- **LAN-IP:** 192.168.178.46 (über Tailscale-Subnet-Route erreichbar)
- **Pairing:** AirPlay + Companion + RAOP, alle 3 Long-Term-Keys aktiv
- **Credentials:** `~/Claude/credentials/AppleTV/dg-wohnzimmer.json` (chmod 600)
- **HA-Integration:** parallel über entry_id `01KS8FHVJFTD6X46QFSQ5B6F2F` aktiv (für AirPlay/Volume; Companion-Befehle gehen über atv-dg)

## tvOS-26.x-Bug-Workaround
pyatv ≤ 0.17.0 ruft beim Initialize Companion's `FetchAttentionState` — tvOS 26.5 antwortet nicht (Bug oder Protokoll-Change), pyatv tearet die Verbindung. **Patch** ignoriert den Failure und behält Companion am Leben:

```
patches/apply_tvos26_fix.sh  # idempotent, kann nach jedem pyatv-Update neu laufen
```

## Wrapper-Befehl
```bash
# Globaler Symlink
~/.local/bin/atv-dg <pyatv-command>

# Beispiele
atv-dg launch_app=com.netflix.Netflix       # App starten
atv-dg launch_app=com.google.ios.youtube    # YouTube
atv-dg launch_app=com.amazon.aiv.AIVApp     # Prime Video
atv-dg launch_app=de.telekom.magentatv      # Magenta TV
atv-dg menu                                  # Menu-Button (Back)
atv-dg home                                  # Home-Button
atv-dg select                                # OK/Select
atv-dg up / down / left / right             # Pfeiltasten
atv-dg play_pause
atv-dg volume_up / volume_down
atv-dg set_volume=0.5                       # 50% Lautstärke
atv-dg power_state                          # tvOS-26-Bug, gibt "Unknown"
```

## Häufige Bundle-IDs
- `com.netflix.Netflix` — Netflix
- `com.amazon.aiv.AIVApp` — Amazon Prime Video
- `com.google.ios.youtube` — YouTube
- `de.telekom.magentatv` — Magenta TV
- `com.apple.TVAppStore` — App Store
- `com.apple.TVSettings` — Einstellungen
- `com.apple.TVHomeSharing` — Home
- `com.spotify.client` — Spotify (falls installiert)

## Was funktioniert (mit tvOS-26-Patch)
- ✅ `launch_app=<bundle>` (App starten)
- ✅ `menu`, `home`, `select`, `up/down/left/right` (Navigation)
- ✅ `set_volume`, `volume_up`, `volume_down` (AirPlay)
- ✅ `play`, `pause`, `play_pause`, `stop` (Media)
- ✅ `screensaver` (Bildschirmschoner aktivieren)

## Was nicht funktioniert (tvOS-26-Bug)
- ❌ `app_list` (`FetchLaunchableApplicationsEvent` schlägt fehl)
- ❌ `power_state`-Read (`FetchAttentionState` schlägt fehl, gibt "Unknown")
- ❌ `current_app` (gleicher Mechanismus)

## Limitationen
- iOS-App-Store-Authentifizierung kann remote nicht bestätigt werden (Touch-ID-Push)
- Verschlüsselte Streams (z.B. Netflix-Inhalte) brauchen App-eigenes Login
- Apple-TV-Reboot via Companion ist nicht supportet (HW-Tasten an Remote nötig)

## Integration in HA (LIVE seit 2026-05-22)

**Architektur:** HTTP-Wrapper (`wrapper/server.py`, Flask) als systemd-User-Service auf claude-code-server (`100.109.100.33:9876`). Bonn-HA (Docker, network_mode=host) ruft per `rest_command:` darauf zu. Esslingen-HA (auf NUC) hat KEINE Route zu `100.109.100.33` (HA-OS-Container ohne Tailscale-Add-on), daher dort KEINE Integration — Bonn-HA sieht Esslinger Entities ohnehin via Federation und reicht.

**Files:**
- Wrapper: `~/Claude/cli-tools/AppleTV_Control/wrapper/server.py` (+ `README.md`)
- systemd-Unit: `~/.config/systemd/user/atv-wrapper.service`
- Auth-Token: `~/Claude/credentials/AppleTV/wrapper-token.json` (chmod 600)
- HA-Package: `~/Claude/projects/Percy_Privat_Projekte/Home_Automatisierung_Bonn/homeassistant/config/packages/atv_dg_esslingen.yaml`
- HA-Dashboard-View: `dashboards/castor_home.yaml` → Tab "Apple TV DG"

**Bonn-HA-Entities:** `sensor.dg_apple_tv_app|lautstarke_wrapper|playing_state` (polling 60s) + 14 `script.dg_atv_*`-Convenience-Skripte.

```bash
# Service-Management
systemctl --user status atv-wrapper
journalctl --user -u atv-wrapper -f
```

## Wiederherstellung bei kompletter Pairing-Drift
1. Apple TV reboot (Menu + Home 6 Sek halten)
2. HA-UI → Settings → Devices → Apple TV → "DG Wohnzimmer (2)" → DELETE
3. HA: neuer apple_tv config flow, IP 192.168.178.46
4. 3 PINs eingeben (AirPlay, Companion, RAOP)
5. Neue Credentials aus HA-Storage extrahieren:
   ```bash
   ssh -i ~/.ssh/id_ed25519_esslingen -p 22222 root@100.121.183.6 \
     "cat /config/.storage/core.config_entries" | jq '.data.entries[] | select(.title=="DG Wohnzimmer (2)") | .data.credentials'
   ```
6. JSON in `~/Claude/credentials/AppleTV/dg-wohnzimmer.json` updaten (Felder 3=AirPlay, 4=Companion, 5=RAOP)
7. Patch erneut anwenden falls pyatv-venv frisch: `~/Claude/cli-tools/AppleTV_Control/patches/apply_tvos26_fix.sh`

## Audio-Routing zu HomePod "DG Wohnzimmer" (seit 2026-05-22)
Apple TV kann sein Audio per AirPlay an den HomePod Mini "HomePod Percys Wohnzimmer" (192.168.178.62, AirPlay-ID `0A:38:9B:1E:D1:B8`, FB-MAC `E0:2B:96:B0:7D:5B`) routen. Companion-Init bricht auf tvOS 26.5 — der Audio-Wrapper nutzt nur AirPlay+RAOP, das reicht.

```bash
atv-dg-audio list           # aktuelle Audio-Outputs anzeigen
atv-dg-audio homepod-on     # HomePod als alleinige Audio-Senke setzen
atv-dg-audio homepod-off    # HomePod entfernen → zurück auf TV-Lautsprecher (HDMI)
atv-dg-audio both           # HomePod + Apple TV parallel (Multi-Output)
atv-dg-audio add-homepod    # HomePod additiv zur aktuellen Liste
atv-dg-audio info           # IDs & IPs aus Credentials anzeigen
atv-dg-audio id             # nur Apple-TV-AirPlay-ID
```

**Daily-Use-Wrapper** der vor jedem `launch_app` HomePod-Routing garantiert:
```bash
atv-dg-with-homepod launch_app=com.netflix.Netflix
```
Sicherheits-Check: Bricht ab wenn der Apple TV gerade spielt (Mom-Schutz), damit kein Audio-Cut mitten in Wiedergabe.

**Persistenz:** AirPlay-Routing wird vom Apple TV gespeichert, kann aber nach Reboot oder längerer Standby-Zeit verloren gehen. Bei Bedarf einfach erneut `atv-dg-audio homepod-on` aufrufen — idempotent.

**Default-State (Stand 2026-05-22):** Keine externen Outputs gesetzt — Audio läuft über TV-HDMI-Lautsprecher.

## Files
- `bin/atv-dg` — Wrapper-Script (Companion+AirPlay+RAOP)
- `bin/atv-dg-audio` — Audio-Routing-Subcommands (AirPlay+RAOP only)
- `bin/atv-dg-with-homepod` — Daily-Use-Wrapper mit Auto-HomePod-Routing
- `venv/` — Python-venv mit pyatv 0.17.0 (gepatcht)
- `patches/apply_tvos26_fix.sh` — tvOS-26-Companion-Fix
- `README.md` — diese Datei
- `~/Claude/credentials/AppleTV/dg-wohnzimmer.json` — Credentials inkl. HomePod-ID (chmod 600)
- `~/.local/bin/atv-dg`, `atv-dg-audio`, `atv-dg-with-homepod` — Symlinks

## Zukunft
- Beobachten ob pyatv 0.18+ den tvOS-26-Fix nativ einbaut → dann Patch obsolet
- Bei tvOS-Update auf 26.6+ erneut testen + Patch ggf. anpassen
