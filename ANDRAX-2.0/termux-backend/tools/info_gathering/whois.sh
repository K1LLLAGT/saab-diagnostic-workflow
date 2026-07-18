#!/usr/bin/env bash
# ANDRAX 2.0 :: Information Gathering :: whois
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/toolkit.sh"
ANDRAX_TOOL_NAME="whois"
read -r -d '' USAGE <<'EOF'
whois.sh — domain / IP registration lookup

USAGE:
    whois.sh <domain-or-ip>

EXAMPLES:
    whois.sh example.com
    whois.sh 8.8.8.8
EOF
andrax_usage_guard "$#"
andrax_init "$ANDRAX_TOOL_NAME"
andrax_need whois "pkg install whois"
out="$(andrax_loot "whois.txt")"
andrax_run whois "$@" | tee "$out" >/dev/null
andrax_log "Saved to $out"
