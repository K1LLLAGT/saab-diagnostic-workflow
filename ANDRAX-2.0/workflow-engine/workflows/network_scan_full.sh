#!/usr/bin/env bash
# ANDRAX 2.0 :: Workflow :: network_scan_full
# All-ports discovery -> service/version + default NSE on open ports.
set -uo pipefail
_wf="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$_wf/../../termux-backend/config/paths.sh"
. "$ANDRAX_WORKFLOW_DIR/libs/logging.sh"
. "$ANDRAX_WORKFLOW_DIR/libs/prompts.sh"
. "$ANDRAX_WORKFLOW_DIR/libs/helpers.sh"

usage() { echo "usage: network_scan_full.sh <host-or-cidr>"; }
[ $# -ge 1 ] || { usage; exit 1; }
target="$1"

require_scope "$target" || exit 1
log_step "Full network scan: $target"

log_step "1/2 fast all-ports discovery (connect scan; no root needed)"
run_tool nmap -sT -p- --min-rate 1000 -oG - "$target" || log_warn "port sweep failed"

log_step "2/2 service/version + default scripts (top 1000)"
run_tool nmap -sT -sV -sC --top-ports 1000 "$target" || log_warn "service scan failed"

log_ok "network_scan_full complete. Logs: $WF_LOG"
