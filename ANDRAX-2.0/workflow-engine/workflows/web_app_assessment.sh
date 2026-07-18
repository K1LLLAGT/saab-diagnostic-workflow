#!/usr/bin/env bash
# ANDRAX 2.0 :: Workflow :: web_app_assessment
# content discovery -> nikto -> sqlmap smoke test.
set -uo pipefail
_wf="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$_wf/../../termux-backend/config/paths.sh"
. "$ANDRAX_WORKFLOW_DIR/libs/logging.sh"
. "$ANDRAX_WORKFLOW_DIR/libs/prompts.sh"
. "$ANDRAX_WORKFLOW_DIR/libs/helpers.sh"

usage() { echo "usage: web_app_assessment.sh <url>  (e.g. http://target/)"; }
[ $# -ge 1 ] || { usage; exit 1; }
url="$1"
host="$(printf '%s' "$url" | sed -E 's#^[a-z]+://##; s#/.*$##')"

require_scope "$host" || exit 1

log_step "Web app assessment: $url"

log_step "1/3 content discovery"
run_tool dirb "$url" || log_warn "content discovery failed"

log_step "2/3 nikto"
run_tool nikto -h "$url" || log_warn "nikto failed"

log_step "3/3 sqlmap crawl smoke test (safe, --batch, low risk/level)"
if confirm "Run sqlmap crawl against $url (authorized targets only)?"; then
    run_tool sqlmap -u "$url" --batch --crawl=1 --level=1 --risk=1 --smart \
        || log_warn "sqlmap failed"
else
    log_info "sqlmap step skipped by user."
fi

log_ok "web_app_assessment complete. Logs: $WF_LOG"
