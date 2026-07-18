#!/usr/bin/env bash
# ANDRAX 2.0 — list tools from the registry, optionally filtered by category.
# USAGE: list_tools.sh [category-id]
set -euo pipefail
_self="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$_self/../../termux-backend/config/paths.sh"
command -v jq >/dev/null 2>&1 || { echo "jq required (pkg install jq)"; exit 2; }

# Pretty-print tab-separated rows; fall back to plain tabs if `column` is absent.
_cols() { if command -v column >/dev/null 2>&1; then column -t -s"$(printf '\t')"; else cat; fi; }

if [ $# -ge 1 ]; then
    jq -r --arg c "$1" '
      .categories[] | select(.id==$c) |
      "== \(.name) ==",
      (.tools[] | "  \(.id)\t\(.name)\t\(.description)")
    ' "$ANDRAX_REGISTRY" | _cols
else
    jq -r '
      .categories[] |
      "== \(.name) (\(.id)) ==",
      (.tools[] | "  \(.id)\t\(.name)\t\(.description)")
    ' "$ANDRAX_REGISTRY" | _cols
fi
