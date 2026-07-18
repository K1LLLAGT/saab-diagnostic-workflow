#!/usr/bin/env bash
# ANDRAX 2.0 :: Reporting :: generate_report
# Assemble a Markdown engagement report from the run's logs + loot.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/toolkit.sh"
ANDRAX_TOOL_NAME="generate_report"
read -r -d '' USAGE <<'EOF'
generate_report.sh — build a Markdown report from logs + loot

USAGE:
    generate_report.sh [engagement-name]

Collects everything under ~/.andrax/logs and ~/.andrax/loot into a single
timestamped Markdown report in the loot directory. Convert it to HTML with
markdown_to_html.sh.

EXAMPLE:
    generate_report.sh "AcmeCorp external test"
EOF
andrax_init "$ANDRAX_TOOL_NAME"
name="${1:-ANDRAX 2.0 Engagement}"
report="$(andrax_loot "report.md")"
{
    echo "# $name"
    echo
    echo "_Generated: $(date -Is) — ANDRAX 2.0_"
    echo
    echo "> Authorized testing only. This report documents findings from tools"
    echo "> run within the engagement scope."
    echo
    echo "## Tool run logs"
    echo
    if compgen -G "$ANDRAX_LOG_DIR/*.log" >/dev/null; then
        for f in "$ANDRAX_LOG_DIR"/*.log; do
            echo "### $(basename "$f")"
            echo '```'
            tail -n 200 "$f"
            echo '```'
            echo
        done
    else
        echo "_No logs found in $ANDRAX_LOG_DIR._"
    fi
    echo "## Captured artifacts (loot)"
    echo
    if [ -d "$ANDRAX_LOOT_DIR" ]; then
        find "$ANDRAX_LOOT_DIR" -type f | sort | sed 's/^/- /'
    else
        echo "_No loot captured._"
    fi
} > "$report"
andrax_log "Report written: $report"
printf '%s\n' "$report"
