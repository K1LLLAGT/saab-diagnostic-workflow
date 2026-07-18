#!/usr/bin/env bash
# ANDRAX 2.0 — common workflow helpers.
# Source: . "$ANDRAX_WORKFLOW_DIR/libs/helpers.sh"

# Ensure ANDRAX paths are available even if env.sh wasn't sourced.
if [ -z "${ANDRAX_HOME:-}" ]; then
    _h_self="${BASH_SOURCE[0]:-$0}"
    _h_dir="$(cd "$(dirname "$_h_self")" && pwd)"
    . "$_h_dir/../../termux-backend/config/paths.sh"
fi

# run_tool <id> [args...] — invoke a registry tool through the launcher.
run_tool() {
    bash "$ANDRAX_LAUNCHER_DIR/launch_tool.sh" "$1" -- "${@:2}"
}

# have <bin> — true if a command exists.
have() { command -v "$1" >/dev/null 2>&1; }

# http_title <url> — best-effort page <title>, using curl.
http_title() {
    local url="$1"
    have curl || { echo "(curl not installed)"; return; }
    curl -s -L --max-time 15 -A "${ANDRAX_HTTP_UA:-ANDRAX-2.0}" "$url" \
        | grep -oiE '<title>[^<]*</title>' | head -n1 | sed -E 's/<\/?title>//gi'
}

# workflow_loot <name> — path for a workflow artifact under loot.
workflow_loot() {
    local d="${ANDRAX_LOOT_DIR:-$HOME/.andrax/loot}/workflows"
    mkdir -p "$d"
    printf '%s/%s-%s\n' "$d" "$(date +%Y%m%d-%H%M%S)" "${1:-out}"
}
