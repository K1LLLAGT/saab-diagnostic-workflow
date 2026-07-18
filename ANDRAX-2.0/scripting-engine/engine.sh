#!/usr/bin/env bash
# ANDRAX 2.0 — scripting engine (single entrypoint).
# This is the `andrax` command. It ties together the registry, the launcher,
# the workflow engine, and environment self-checks.
#
# USAGE:
#   andrax <command> [args...]
#
# COMMANDS:
#   doctor                         environment self-check
#   list-tools [category]          list tools (optionally by category)
#   list-workflows                 list workflows
#   categories                     list categories
#   run-tool <id> -- <args...>     run a tool by id
#   run-workflow <id> -- <args...> run a workflow by id
#   info <tool-id>                 show tool details from the registry
#   help                           this message
set -euo pipefail

ENGINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$ENGINE_DIR/../termux-backend/config/paths.sh"

_need_jq() { command -v jq >/dev/null 2>&1 || { echo "andrax: jq required (pkg install jq)"; exit 2; }; }

usage() { sed -n '2,20p' "$ENGINE_DIR/engine.sh" | sed 's/^# \{0,1\}//'; }

cmd="${1:-help}"; shift || true
case "$cmd" in
    help|-h|--help) usage ;;

    doctor)
        echo "ANDRAX 2.0 doctor"
        echo "  ANDRAX_HOME = $ANDRAX_HOME"
        echo "  registry    = $ANDRAX_REGISTRY $( [ -f "$ANDRAX_REGISTRY" ] && echo OK || echo MISSING )"
        echo "  log dir     = $ANDRAX_LOG_DIR"
        echo "  loot dir    = $ANDRAX_LOOT_DIR"
        echo "  root?       = $( [ "$(id -u)" -eq 0 ] && echo yes || echo 'no (connect-scan fallbacks active)' )"
        echo "  core tools:"
        for t in jq nmap whois dig sqlmap hydra john binwalk strings mitmproxy msfconsole; do
            printf '    %-12s %s\n' "$t" "$(command -v "$t" >/dev/null 2>&1 && echo present || echo '-')"
        done
        echo "  proot userland ($ANDRAX_PROOT_DISTRO):"
        if command -v proot-distro >/dev/null 2>&1 && proot-distro list 2>/dev/null | grep -q "$ANDRAX_PROOT_DISTRO"; then
            echo "    installed"
        else
            echo "    not installed (run termux-backend/setup/setup_proot_kali.sh)"
        fi
        ;;

    list-tools)   _need_jq; bash "$ENGINE_DIR/scripts/list_tools.sh" "$@" ;;
    list-workflows) _need_jq; bash "$ENGINE_DIR/scripts/list_workflows.sh" "$@" ;;
    categories)   bash "$ANDRAX_LAUNCHER_DIR/category_dispatch.sh" "$@" ;;

    run-tool)     bash "$ENGINE_DIR/scripts/run_tool_by_id.sh" "$@" ;;
    run-workflow) bash "$ENGINE_DIR/scripts/run_workflow_by_id.sh" "$@" ;;

    info)
        _need_jq
        [ $# -ge 1 ] || { echo "usage: andrax info <tool-id>"; exit 1; }
        jq -r --arg id "$1" '
          .categories[] as $c | $c.tools[] | select(.id==$id) |
          "Tool:        \(.name) (\(.id))",
          "Category:    \($c.name)",
          "Script:      \(.script)",
          "Description: \(.description)",
          "Example:     andrax \(.example)"
        ' "$ANDRAX_REGISTRY" || echo "unknown tool '$1'"
        ;;

    *) echo "andrax: unknown command '$cmd'"; echo; usage; exit 1 ;;
esac
