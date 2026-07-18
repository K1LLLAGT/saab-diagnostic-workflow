#!/usr/bin/env bash
# ANDRAX 2.0 — workflow logging library.
# Source from any workflow: . "$ANDRAX_WORKFLOW_DIR/libs/logging.sh"

: "${ANDRAX_LOG_DIR:=$HOME/.andrax/logs}"
mkdir -p "$ANDRAX_LOG_DIR"

WF_LOG="${WF_LOG:-$ANDRAX_LOG_DIR/workflow-$(date +%Y%m%d-%H%M%S).log}"

_c() { case "$1" in red) printf '\033[31m';; grn) printf '\033[32m';; ylw) printf '\033[33m';; blu) printf '\033[34m';; *) printf '';; esac; }
_rst() { printf '\033[0m'; }

log_info()  { local m="[*] $*"; echo "$(_c blu)$m$(_rst)"; echo "[$(date +%T)] INFO  $*" >>"$WF_LOG"; }
log_ok()    { local m="[+] $*"; echo "$(_c grn)$m$(_rst)"; echo "[$(date +%T)] OK    $*" >>"$WF_LOG"; }
log_warn()  { local m="[!] $*"; echo "$(_c ylw)$m$(_rst)"; echo "[$(date +%T)] WARN  $*" >>"$WF_LOG"; }
log_err()   { local m="[x] $*"; echo "$(_c red)$m$(_rst)" >&2; echo "[$(date +%T)] ERROR $*" >>"$WF_LOG"; }
log_step()  { echo; echo "$(_c blu)==== $* ====$(_rst)"; echo "[$(date +%T)] STEP  $*" >>"$WF_LOG"; }
