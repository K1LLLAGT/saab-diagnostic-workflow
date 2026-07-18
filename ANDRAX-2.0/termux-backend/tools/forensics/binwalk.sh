#!/usr/bin/env bash
# ANDRAX 2.0 :: Forensics :: binwalk
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/toolkit.sh"
ANDRAX_TOOL_NAME="binwalk"
read -r -d '' USAGE <<'EOF'
binwalk.sh — firmware / binary analysis & extraction

USAGE:
    binwalk.sh <file> [binwalk args...]

EXAMPLES:
    binwalk.sh firmware.bin              # signature scan
    binwalk.sh -e firmware.bin           # extract embedded files (into loot)
EOF
andrax_usage_guard "$#"
andrax_init "$ANDRAX_TOOL_NAME"
andrax_need binwalk "pkg install binwalk"
outdir="$ANDRAX_LOOT_DIR/binwalk"
mkdir -p "$outdir"
( cd "$outdir" && : )
andrax_run binwalk --directory "$outdir" "$@"
andrax_log "Extractions (if any) under $outdir"
