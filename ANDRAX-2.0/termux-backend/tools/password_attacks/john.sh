#!/usr/bin/env bash
# ANDRAX 2.0 :: Password Attacks :: john
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/toolkit.sh"
ANDRAX_TOOL_NAME="john"
read -r -d '' USAGE <<'EOF'
john.sh — offline password hash cracking (John the Ripper)

USAGE:
    john.sh <hashfile> [john args...]

EXAMPLES:
    john.sh hashes.txt --wordlist=rockyou.txt
    john.sh hashes.txt --format=raw-md5 --show

For hashcat (GPU-less on-device CPU) use the exploitation/hashcat path instead.
EOF
andrax_usage_guard "$#"
andrax_init "$ANDRAX_TOOL_NAME"
andrax_need john "pkg install john"
andrax_run john "$@"
