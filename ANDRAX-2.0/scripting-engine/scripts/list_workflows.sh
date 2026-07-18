#!/usr/bin/env bash
# ANDRAX 2.0 — list workflows from the registry.
# USAGE: list_workflows.sh
set -euo pipefail
_self="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$_self/../../termux-backend/config/paths.sh"
command -v jq >/dev/null 2>&1 || { echo "jq required (pkg install jq)"; exit 2; }
_cols() { if command -v column >/dev/null 2>&1; then column -t -s"$(printf '\t')"; else cat; fi; }

jq -r '
  "ANDRAX 2.0 workflows:",
  (.workflows[] | "  \(.id)\t\(.name)\t\(.description)")
' "$ANDRAX_REGISTRY" | _cols
