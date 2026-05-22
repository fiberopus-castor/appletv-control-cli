# appletv-dg MCP server

Thin stdio MCP wrapper around the `atv-dg` CLI. Lets Claude Code (and any
other MCP client) control the Apple TV "DG Wohnzimmer Esslingen" via
typed tool calls instead of shelling out to `bash`.

## Tools
| Tool | Purpose |
|---|---|
| `appletv_dg_launch_app(bundle_id)` | Launch app by bundle id |
| `appletv_dg_navigate(key)` | Send remote key (home/menu/select/up/down/...) |
| `appletv_dg_volume(action, level?)` | get/set/up/down volume (0-100) |
| `appletv_dg_current_app()` | Current foreground app (often "Unknown" on tvOS-26) |
| `appletv_dg_playing()` | Playing state, title, position, duration |
| `appletv_dg_text_input(text)` | Append text to virtual keyboard |
| `appletv_dg_audio_route(target)` | homepod / tv / both |
| `appletv_dg_health()` | Latest heartbeat state, alert-flag |

## Local development
```bash
~/Claude/cli-tools/AppleTV_Control/venv/bin/python \
  ~/Claude/cli-tools/AppleTV_Control/mcp-server/appletv_dg_mcp.py
```
The server speaks MCP/stdio — for a smoke-test, send an `initialize`
request on stdin, or just verify import:
```bash
~/Claude/cli-tools/AppleTV_Control/venv/bin/python -c \
  "import mcp_server.appletv_dg_mcp as m; print(m.VERSION)" 2>&1
```

## Registration in Claude Code
Add to `~/.claude.json` under `mcpServers`:
```json
"appletv-dg": {
  "type": "stdio",
  "command": "/home/pol/Claude/cli-tools/AppleTV_Control/mcp-server/run.sh"
}
```
Restart Claude Code → tools appear as `mcp__appletv-dg__*`.
