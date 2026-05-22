#!/bin/bash
# SPDX-License-Identifier: MIT
# Launcher for the appletv-dg stdio MCP server.
# Uses the project venv (which has `mcp` installed alongside pyatv).
set -e
ROOT="$(dirname "$(dirname "$(readlink -f "$0")")")"
exec "$ROOT/venv/bin/python" "$ROOT/mcp-server/appletv_dg_mcp.py" "$@"
