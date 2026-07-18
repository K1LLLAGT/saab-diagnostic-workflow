#!/usr/bin/env bash
# ANDRAX 2.0 :: Reporting :: markdown_to_html
# Convert a Markdown report to a standalone, styled HTML file. Uses pandoc if
# present, else a small built-in converter (headings/code/lists/paragraphs).
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/toolkit.sh"
ANDRAX_TOOL_NAME="markdown_to_html"
read -r -d '' USAGE <<'EOF'
markdown_to_html.sh — render a Markdown report to HTML

USAGE:
    markdown_to_html.sh <report.md> [out.html]

EXAMPLE:
    markdown_to_html.sh ~/.andrax/loot/generate_report/*-report.md
EOF
andrax_usage_guard "$#"
andrax_init "$ANDRAX_TOOL_NAME"
md="$1"
[ -f "$md" ] || andrax_die "markdown file '$md' not found"
html="${2:-${md%.md}.html}"

if command -v pandoc >/dev/null 2>&1; then
    andrax_run pandoc -s --metadata title="ANDRAX 2.0 Report" -o "$html" "$md"
else
    andrax_log "pandoc not installed; using built-in minimal converter."
    {
        cat <<'HEAD'
<!doctype html><html><head><meta charset="utf-8">
<title>ANDRAX 2.0 Report</title>
<style>
 body{font:15px/1.5 system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#111;background:#fff}
 h1,h2,h3{line-height:1.2}code,pre{font-family:ui-monospace,monospace}
 pre{background:#f4f4f4;padding:1rem;overflow:auto;border-radius:6px}
 blockquote{border-left:4px solid #c00;margin:0;padding:.2rem 1rem;color:#555}
</style></head><body>
HEAD
        awk '
          BEGIN{incode=0}
          /^```/{ if(incode){print "</pre>";incode=0} else {print "<pre>";incode=1} next }
          incode{ gsub(/&/,"\\&amp;"); gsub(/</,"\\&lt;"); print; next }
          /^### /{ sub(/^### /,""); print "<h3>" $0 "</h3>"; next }
          /^## /{ sub(/^## /,""); print "<h2>" $0 "</h2>"; next }
          /^# /{ sub(/^# /,""); print "<h1>" $0 "</h1>"; next }
          /^> /{ sub(/^> /,""); print "<blockquote>" $0 "</blockquote>"; next }
          /^- /{ sub(/^- /,""); print "<li>" $0 "</li>"; next }
          /^[[:space:]]*$/{ print "<p></p>"; next }
          { print "<p>" $0 "</p>" }
        ' "$md"
        echo "</body></html>"
    } > "$html"
fi
andrax_log "HTML report: $html"
printf '%s\n' "$html"
