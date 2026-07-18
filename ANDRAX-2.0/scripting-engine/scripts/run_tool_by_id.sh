#!/usr/bin/env bash
# ANDRAX 2.0 — run a tool by id (thin wrapper over the launcher).
# USAGE: run_tool_by_id.sh <tool-id> [-- <tool args...>]
set -euo pipefail
_self="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$_self/../../termux-backend/config/paths.sh"

[ $# -ge 1 ] || { echo "usage: run-tool <tool-id> -- <args...>"; exit 1; }
exec bash "$ANDRAX_LAUNCHER_DIR/launch_tool.sh" "$@"
