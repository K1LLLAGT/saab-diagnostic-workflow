#!/usr/bin/env bash
# ANDRAX 2.0 :: Password Attacks :: hydra
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/toolkit.sh"
ANDRAX_TOOL_NAME="hydra"
read -r -d '' USAGE <<'EOF'
hydra.sh — online login brute-forcing (THC-Hydra)

USAGE:
    hydra.sh <hydra-args...>

EXAMPLES:
    hydra.sh -l admin -P rockyou.txt ssh://10.0.0.5
    hydra.sh -L users.txt -P pass.txt ftp://target

AUTHORIZED TESTING ONLY. Online brute force is noisy and can lock accounts.
EOF
andrax_usage_guard "$#"
andrax_init "$ANDRAX_TOOL_NAME"
andrax_need hydra "pkg install hydra"
out="$(andrax_loot "hydra.txt")"
andrax_run hydra -o "$out" "$@"
andrax_log "Saved to $out"
