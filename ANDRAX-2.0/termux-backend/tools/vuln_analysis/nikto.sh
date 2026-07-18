#!/usr/bin/env bash
# ANDRAX 2.0 :: Vulnerability Analysis :: nikto
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/toolkit.sh"
ANDRAX_TOOL_NAME="nikto"
read -r -d '' USAGE <<'EOF'
nikto.sh — web server vulnerability scanner

USAGE:
    nikto.sh -h <url>  [extra nikto args...]

EXAMPLES:
    nikto.sh -h http://target.example
    nikto.sh -h https://target.example -Tuning 1234b
EOF
andrax_usage_guard "$#"
andrax_init "$ANDRAX_TOOL_NAME"
if command -v nikto >/dev/null 2>&1; then
    out="$(andrax_loot "nikto.txt")"
    andrax_run nikto "$@" -o "$out"
    andrax_log "Saved to $out"
else
    andrax_log "nikto not in Termux; running via proot userland."
    andrax_proot nikto "$@"
fi
