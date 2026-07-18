#!/usr/bin/env bash
# ANDRAX 2.0 :: Vulnerability Analysis :: sqlmap
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/toolkit.sh"
ANDRAX_TOOL_NAME="sqlmap"
read -r -d '' USAGE <<'EOF'
sqlmap.sh — automatic SQL injection detection & exploitation

USAGE:
    sqlmap.sh -u "<url-with-param>" [sqlmap args...]

EXAMPLES:
    sqlmap.sh -u "http://target/item?id=1" --batch --dbs
    sqlmap.sh -u "http://target/login" --data "user=a&pass=b" --batch

AUTHORIZED TESTING ONLY. Point this only at targets you own or are scoped to.
EOF
andrax_usage_guard "$#"
andrax_init "$ANDRAX_TOOL_NAME"
andrax_need sqlmap "pkg install sqlmap"
outdir="$ANDRAX_LOOT_DIR/sqlmap"
mkdir -p "$outdir"
andrax_run sqlmap --output-dir="$outdir" "$@"
andrax_log "Session/output under $outdir"
