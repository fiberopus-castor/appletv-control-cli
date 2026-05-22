# Changelog

All notable changes to AppleTV_Control will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] — 2026-05-22

### Fixed
- **MCP handshake breakage**: removed `sys.stdout = sys.stderr` reassignment in `mcp-server/appletv_dg_mcp.py`. The stdio MCP transport requires stdout to remain bound to the FastMCP JSON-RPC writer; reassigning it silently sent the `initialize` response into the void, causing the client to time out after 30 s. Stray output must instead be silenced at its source (logging is already pinned to stderr).

## [0.1.0] — 2026-05-22

Initial public release.

### Added
- `bin/atv-dg` — persistent pyatv wrapper with AirPlay + Companion + RAOP credentials.
- `bin/atv-dg-audio` — audio-output routing helper (HomePod on/off/both, AirPlay+RAOP only).
- `bin/atv-dg-with-homepod` — daily-use wrapper that ensures HomePod routing before each launch_app.
- `bin/atv-dg-heartbeat` — read-only Companion-Heartbeat (volume read), JSONL-log + alert-flag, no power-wake.
- `patches/apply_tvos26_fix.sh` — idempotent pyatv patch fixing tvOS-26.x `FetchAttentionState` timeout.
- `wrapper/server.py` — Flask REST wrapper for Home Assistant integration (bearer-token-auth).
- `mcp-server/` — stdio MCP server exposing 8 tools (`launch_app`, `navigate`, `volume`, `current_app`, `playing`, `text_input`, `audio_route`, `health`).
- README.md, CHANGELOG.md, LICENSE (MIT), INTEGRATION.md.

### Known issues
- tvOS-26.x bug: `power_state`, `current_app`, `app_list` return "Unknown" (FetchAttentionState protocol break).
- iOS App-Store auth (Touch-ID push) cannot be confirmed remote.
- HW-reboot of Apple TV not supported via Companion (use physical remote).

### Security
- Credentials kept outside the repo under `~/Claude/credentials/AppleTV/` (chmod 600).
- `.gitignore` blocks accidental commit of any `*credentials*.json`, `*token*.json`, `wrapper-token*`.
