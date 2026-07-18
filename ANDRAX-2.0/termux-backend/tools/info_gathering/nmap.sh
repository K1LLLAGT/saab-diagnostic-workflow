#!/usr/bin/env bash
# ANDRAX 2.0 :: Information Gathering :: nmap
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/toolkit.sh"
ANDRAX_TOOL_NAME="nmap"
read -r -d '' USAGE <<'EOF'
nmap.sh — network & service discovery (Nmap)

USAGE:
    nmap.sh <nmap-args...>

EXAMPLES:
    nmap.sh -sV scanme.nmap.org           # service/version detection
    nmap.sh -sC -sV -oN scan.txt 10.0.0.5 # default scripts + version
    nmap.sh -p- --min-rate 1000 target    # all ports

NOTE (non-root Android): SYN scan (-sS) needs raw sockets/root. Without root
this wrapper falls back to a TCP connect scan (-sT) automatically.
EOF
andrax_usage_guard "$#"
andrax_init "$ANDRAX_TOOL_NAME"
andrax_need nmap "pkg install nmap"

args=("$@")
if [ "$(id -u)" -ne 0 ]; then
    for a in "${args[@]}"; do
        if [ "$a" = "-sS" ]; then
            andrax_log "No root: rewriting -sS (SYN) to -sT (connect scan)."
            args=("${args[@]/-sS/-sT}")
            break
        fi
    done
fi
andrax_run nmap "${args[@]}"
