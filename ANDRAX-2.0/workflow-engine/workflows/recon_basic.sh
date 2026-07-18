#!/usr/bin/env bash
# ANDRAX 2.0 :: Workflow :: recon_basic
# whois -> DNS enumeration -> nmap service scan -> HTTP title.
set -uo pipefail
_wf="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$_wf/../../termux-backend/config/paths.sh"
. "$ANDRAX_WORKFLOW_DIR/libs/logging.sh"
. "$ANDRAX_WORKFLOW_DIR/libs/prompts.sh"
. "$ANDRAX_WORKFLOW_DIR/libs/helpers.sh"

usage() { echo "usage: recon_basic.sh <domain-or-host>"; }
[ $# -ge 1 ] || { usage; exit 1; }
target="$1"

require_scope "$target" || exit 1

log_step "Basic recon: $target"

log_step "1/4 whois"
run_tool whois "$target" || log_warn "whois failed"

log_step "2/4 DNS enumeration"
run_tool dnsenum "$target" || log_warn "dnsenum failed"

log_step "3/4 nmap top-ports service scan"
run_tool nmap -sT -sV --top-ports 100 "$target" || log_warn "nmap failed"

log_step "4/4 HTTP title"
for scheme in http https; do
    t="$(http_title "$scheme://$target")"
    [ -n "$t" ] && log_ok "$scheme title: $t"
done

log_ok "recon_basic complete. Logs: $WF_LOG"
