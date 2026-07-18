#!/usr/bin/env bash
# ANDRAX 2.0 — central tool launcher.
# Resolves a tool by id (or name) in tool_registry.json and runs its script,
# passing through all remaining arguments. Used by the engine, the CLI, and the
# Android app bridge.
#
# USAGE:
#   launch_tool.sh <tool-id> [-- <tool args...>]
#   launch_tool.sh --list
set -euo pipefail

_self="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$_self/../termux-backend/config/paths.sh"

command -v jq >/dev/null 2>&1 || { echo "launch_tool: jq is required (pkg install jq)"; exit 2; }
_cols() { if command -v column >/dev/null 2>&1; then column -t -s"$(printf '\t')"; else cat; fi; }

usage() {
    cat <<EOF
launch_tool.sh — resolve and run an ANDRAX tool by id

USAGE:
    launch_tool.sh <tool-id> [-- <args passed to the tool>]
    launch_tool.sh --list

EXAMPLES:
    launch_tool.sh nmap -- -sV scanme.nmap.org
    launch_tool.sh dnsenum -- example.com
EOF
}

[ $# -eq 0 ] && { usage; exit 1; }

if [ "$1" = "--list" ]; then
    jq -r '.categories[].tools[] | "\(.id)\t\(.name)\t\(.description)"' "$ANDRAX_REGISTRY" | _cols
    exit 0
fi

tool_id="$1"; shift || true
# Drop a leading "--" separator if present.
[ "${1:-}" = "--" ] && shift || true

# Look the tool up by id, then fall back to case-insensitive name match.
script_rel="$(jq -r --arg id "$tool_id" '
    (.categories[].tools[] | select(.id == $id) | .script) // empty
' "$ANDRAX_REGISTRY")"

if [ -z "$script_rel" ]; then
    script_rel="$(jq -r --arg id "$tool_id" '
        (.categories[].tools[] | select((.name|ascii_downcase) == ($id|ascii_downcase)) | .script) // empty
    ' "$ANDRAX_REGISTRY" | head -n1)"
fi

[ -n "$script_rel" ] || { echo "launch_tool: unknown tool '$tool_id' (try --list)"; exit 3; }

script_abs="$ANDRAX_TOOLS_DIR/$script_rel"
[ -f "$script_abs" ] || { echo "launch_tool: script not found: $script_abs"; exit 4; }
[ -x "$script_abs" ] || chmod +x "$script_abs" 2>/dev/null || true

exec bash "$script_abs" "$@"
