#!/usr/bin/env bash
# ANDRAX 2.0 :: Forensics :: strings
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/toolkit.sh"
ANDRAX_TOOL_NAME="strings"
read -r -d '' USAGE <<'EOF'
strings.sh — extract printable strings + highlight interesting artifacts

USAGE:
    strings.sh <file> [min-len]

Extracts strings (default min length 6) and greps for URLs, keys, IPs, paths.

EXAMPLE:
    strings.sh suspicious.bin 8
EOF
andrax_usage_guard "$#"
andrax_init "$ANDRAX_TOOL_NAME"
andrax_need strings "pkg install binutils"
file="$1"; minlen="${2:-6}"
[ -f "$file" ] || andrax_die "file '$file' not found"
out="$(andrax_loot "strings.txt")"
strings -n "$minlen" "$file" > "$out"
andrax_log "All strings -> $out"
andrax_log "--- interesting artifacts ---"
grep -Eni 'https?://|[0-9]{1,3}(\.[0-9]{1,3}){3}|api[_-]?key|secret|BEGIN [A-Z ]*PRIVATE KEY|eyJ[A-Za-z0-9_-]{10,}' "$out" | head -n 200 || true
