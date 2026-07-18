#!/usr/bin/env bash
# ANDRAX 2.0 — run a workflow by id.
# USAGE: run_workflow_by_id.sh <workflow-id> [-- <workflow args...>]
set -euo pipefail
_self="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$_self/../../termux-backend/config/paths.sh"
command -v jq >/dev/null 2>&1 || { echo "jq required (pkg install jq)"; exit 2; }

[ $# -ge 1 ] || { echo "usage: run-workflow <workflow-id> -- <args...>"; exit 1; }
wf_id="$1"; shift || true
[ "${1:-}" = "--" ] && shift || true

script_rel="$(jq -r --arg id "$wf_id" '(.workflows[] | select(.id==$id) | .script) // empty' "$ANDRAX_REGISTRY")"
[ -n "$script_rel" ] || { echo "unknown workflow '$wf_id' (try: andrax list-workflows)"; exit 3; }

script_abs="$ANDRAX_WORKFLOW_DIR/workflows/$script_rel"
[ -f "$script_abs" ] || { echo "workflow script not found: $script_abs"; exit 4; }
exec bash "$script_abs" "$@"
