#!/usr/bin/env bash
# ANDRAX 2.0 :: Reverse Engineering :: apkinspect
# Static triage of an APK: manifest, permissions, strings, embedded secrets.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/toolkit.sh"
ANDRAX_TOOL_NAME="apkinspect"
read -r -d '' USAGE <<'EOF'
apkinspect.sh — static APK triage

USAGE:
    apkinspect.sh <app.apk>

WHAT IT DOES:
    * Lists archive contents
    * Extracts AndroidManifest (aapt if available)
    * Pulls printable strings from classes.dex / libs
    * Greps for likely secrets (http urls, api keys, JWTs)

EXAMPLE:
    apkinspect.sh target.apk
EOF
andrax_usage_guard "$#"
andrax_init "$ANDRAX_TOOL_NAME"
apk="$1"
[ -f "$apk" ] || andrax_die "APK '$apk' not found"
andrax_need unzip "pkg install unzip"
andrax_need strings "pkg install binutils"
out="$(andrax_loot "apk-report.txt")"
{
    echo "== contents =="; unzip -l "$apk"
    echo; echo "== manifest (aapt) =="
    if command -v aapt >/dev/null 2>&1; then aapt dump badging "$apk"; else echo "aapt not installed (pkg install aapt)"; fi
    echo; echo "== interesting strings =="
    unzip -p "$apk" classes.dex 2>/dev/null | strings -n 6 | \
        grep -Ei 'https?://|api[_-]?key|secret|password|token|eyJ[A-Za-z0-9_-]{10,}' | sort -u | head -n 400
} | tee "$out"
andrax_log "Report saved to $out"
