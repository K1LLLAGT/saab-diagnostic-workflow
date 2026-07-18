#!/usr/bin/env bash
# ANDRAX 2.0 :: Database Assessment :: dbassess
# Lightweight DB service fingerprinting + optional deeper checks via nmap NSE.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/toolkit.sh"
ANDRAX_TOOL_NAME="dbassess"
read -r -d '' USAGE <<'EOF'
dbassess.sh — database service discovery & assessment

USAGE:
    dbassess.sh <target> [port]

WHAT IT DOES:
    * Scans common DB ports (3306 mysql, 5432 postgres, 1433 mssql,
      27017 mongodb, 6379 redis, 1521 oracle)
    * Runs nmap DB NSE scripts for banner/auth info

EXAMPLE:
    dbassess.sh 10.0.0.20
EOF
andrax_usage_guard "$#"
andrax_init "$ANDRAX_TOOL_NAME"
andrax_need nmap "pkg install nmap"
target="$1"
ports="${2:-3306,5432,1433,27017,6379,1521}"
out="$(andrax_loot "db.txt")"
andrax_run nmap -sT -sV -p "$ports" \
    --script "banner,mysql-info,ms-sql-info,mongodb-info,redis-info,pgsql-brute and safe" \
    -oN "$out" "$target"
andrax_log "Saved to $out"
