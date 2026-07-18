#!/usr/bin/env bash
# ANDRAX 2.0 :: Web Applications :: wpscan
# WPScan is a Ruby gem; runs cleanly inside the proot userland.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/toolkit.sh"
ANDRAX_TOOL_NAME="wpscan"
read -r -d '' USAGE <<'EOF'
wpscan.sh — WordPress security scanner

USAGE:
    wpscan.sh --url <url> [wpscan args...]

EXAMPLES:
    wpscan.sh --url https://blog.example --enumerate vp,u
    wpscan.sh --url https://blog.example --api-token <TOKEN>

Runs inside the proot Kali userland (setup_proot_kali.sh). If wpscan is present
directly in Termux (via gem), it uses that instead.
EOF
andrax_usage_guard "$#"
andrax_init "$ANDRAX_TOOL_NAME"
if command -v wpscan >/dev/null 2>&1; then
    andrax_run wpscan "$@"
else
    andrax_log "Using proot userland for wpscan."
    andrax_proot wpscan "$@"
fi
