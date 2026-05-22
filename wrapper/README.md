# atv-wrapper — HTTP-Wrapper für atv-dg

Kleiner Flask-HTTP-Service, der die `atv-dg`-CLI für Home Assistant verfügbar
macht. Läuft als systemd-User-Service auf claude-code-server und wird von
beiden HA-Instanzen (Bonn-Docker auf claude-code-server selbst, Esslingen-OS
auf NUC) über Tailscale (`http://100.109.100.33:9876`) angesprochen.

Hintergrund: der Bonn-HA-Docker-Container hat keinen Zugriff auf
`/home/pol/.local/bin/atv-dg` (nur `/config` ist gemountet), und der
Esslingen-HA läuft auf einem anderen Host. Ein HTTP-Wrapper ist sauberer und
debugbarer als SSH-from-HA.

## Service

- **Code:** `~/Claude/cli-tools/AppleTV_Control/wrapper/server.py`
- **Python-venv:** `~/Claude/cli-tools/AppleTV_Control/venv/` (Flask 3 + pyatv)
- **systemd-User-Unit:** `~/.config/systemd/user/atv-wrapper.service`
- **Linger aktiv:** `loginctl enable-linger pol` (Start ohne Login)
- **Bind:** `0.0.0.0:9876` — Tailscale-IP `100.109.100.33` reachable, LAN/Public per Firewall-Default nicht durchgereicht; zusätzlich Bearer-Auth.
- **Auth-Token:** `~/Claude/credentials/AppleTV/wrapper-token.json`, Feld `token` (chmod 600).
- **Logs:** `journalctl --user -u atv-wrapper.service -f`

## Endpoints

Alle außer `/healthz` erwarten Header `Authorization: Bearer <token>`.

| Method | Path                  | Body                                       | Beschreibung |
|--------|-----------------------|--------------------------------------------|--------------|
| GET    | `/healthz`            | —                                          | alive + atv-dg-Pfad |
| GET    | `/atv/dg/state`       | —                                          | App, Title, Volume, Playing-State (25s-Cache, Cold-Start ~4-5s, warm ~17ms) |
| POST   | `/atv/dg/launch_app`  | `{"bundle_id":"com.netflix.Netflix"}`      | App starten |
| POST   | `/atv/dg/key`         | `{"key":"home"}`                           | Tastenklick (home/menu/select/up/down/left/right/play_pause/play/pause/stop/volume_up/volume_down/screensaver/turn_on/turn_off/...) |
| POST   | `/atv/dg/volume`      | `{"level":0.5}`                            | 0-1 → set_volume an pyatv |
| POST   | `/atv/dg/audio_output`| `{"devices":["DG HomePod Mini"]}`          | AirPlay-Output (set_output_devices, MAC-IDs nötig) |

Erfolgs-Response: `200 {ok:true, returncode, stdout, stderr, cmd}`
Fehler: `400` (bad input), `401` (kein/falscher Token), `502` (pyatv-Fehler).

## State-Caching

`/atv/dg/state` cached die letzte Antwort 25s, weil 3 sequenzielle pyatv-
Calls (`app`, `playing`, `volume`) jeweils ~4s brauchen (tvOS-26-Companion-
Stall). Mit Cache: ~4-5s erster Call, <20ms folgende Calls bis Ablauf.

## Aufruf von Hand (Beispiele)

```bash
TOKEN="86589d185b227728e16fd262f26dfbc481ce6ce3e2f4e6d5"
HOST="http://100.109.100.33:9876"
curl -s $HOST/healthz | jq .
curl -s -H "Authorization: Bearer $TOKEN" $HOST/atv/dg/state | jq .
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"bundle_id":"com.netflix.Netflix"}' $HOST/atv/dg/launch_app
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"key":"home"}' $HOST/atv/dg/key
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"level":0.4}' $HOST/atv/dg/volume
```

## HA-Integration

Beide HA-Instanzen haben ein Package `packages/atv_dg_esslingen.yaml` mit:
- 4 `rest_command:`-Einträgen (launch_app / key / volume / audio_output)
- 1 `rest:`-Sensor (scan_interval 60s, timeout 30s) → 3 Sensors:
  - `sensor.dg_apple_tv_app` (state = App-Name, attrs: app_id/title/position/playing_state/media_type/volume)
  - `sensor.dg_apple_tv_lautstarke_wrapper` (0-100)
  - `sensor.dg_apple_tv_playing_state` (Playing/Paused/Idle/...)
- 14 Convenience-`script:`-Einträgen für Dashboards (dg_atv_launch_netflix, dg_atv_home, dg_atv_up, ...)

Secret `atv_wrapper_bearer` in beiden `secrets.yaml`-Dateien (Wert inkl. "Bearer "-Prefix).

## Bedienung

```bash
# Service starten/stoppen/neu starten
systemctl --user start atv-wrapper
systemctl --user stop atv-wrapper
systemctl --user restart atv-wrapper
systemctl --user status atv-wrapper

# Logs live
journalctl --user -u atv-wrapper -f

# Token rotieren
# 1) neuen Token in ~/Claude/credentials/AppleTV/wrapper-token.json eintragen
# 2) systemctl --user restart atv-wrapper
# 3) atv_wrapper_bearer in beiden HA-secrets.yaml updaten (inkl. "Bearer "-Prefix)
# 4) HA-Restart auf beiden Seiten
```

## Bekannte Limitierungen

- Erster `/atv/dg/state`-Call kalt 4-5s — HA-REST-Plattform mit `timeout: 30` konfiguriert
- pyatv-Verbose-Output (Companion-tvOS-26-Stall-Trace) landet im Wrapper-`stdout`/`stderr` der subprocess-Calls; nicht user-relevant aber im JSON-Response sichtbar (`*_raw`-Felder)
- `audio_output` nimmt Geräte-IDs (MACs), keine Klartextnamen. Für Klartextnamen erst `output_devices` listen lassen.
- Power-State kann tvOS-26-bedingt nicht abgefragt werden — über `switch.dg_apple_tv_steckdose` (Shelly an Steckdose) als Proxy.
