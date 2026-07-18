#!/usr/bin/env bash
# ANDRAX 2.0 — category dispatcher.
# Lists categories and the tools within them. Used by the Android app to build
# its category screens and by CLI users to browse the arsenal.
#
# USAGE:
#   category_dispatch.sh                 list all categories
#   category_dispatch.sh <category-id>   list tools in a category
#   category_dispatch.sh --json          machine-readable full dump
set -euo pipefail

_self="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$_self/../termux-backend/config/paths.sh"
command -v jq >/dev/null 2>&1 || { echo "category_dispatch: jq required (pkg install jq)"; exit 2; }
_cols() { if command -v column >/dev/null 2>&1; then column -t -s"$(printf '\t')"; else cat; fi; }

if [ "${1:-}" = "--json" ]; then
    jq '.categories' "$ANDRAX_REGISTRY"
    exit 0
fi

if [ $# -eq 0 ]; then
    echo "ANDRAX 2.0 — categories:"
    jq -r '.categories[] | "  \(.id)\t\(.name)\t(\(.tools|length) tools)"' "$ANDRAX_REGISTRY" \
        | _cols
    echo
    echo "Run: category_dispatch.sh <category-id>   to list its tools."
    exit 0
fi

cat_id="$1"
count="$(jq -r --arg c "$cat_id" '[.categories[] | select(.id==$c)] | length' "$ANDRAX_REGISTRY")"
[ "$count" -gt 0 ] || { echo "category_dispatch: unknown category '$cat_id'"; exit 3; }

jq -r --arg c "$cat_id" '
    .categories[] | select(.id==$c) |
    "== \(.name) ==",
    (.tools[] | "  \(.id)\t\(.description)\n     e.g. andrax \(.example)")
' "$ANDRAX_REGISTRY"
