#!/usr/bin/env bash
# ANDRAX 2.0 :: Web Applications :: dirb (content discovery)
# Modern replacement stack: prefers ffuf/gobuster/dirsearch, all Termux-friendly.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/toolkit.sh"
ANDRAX_TOOL_NAME="dirb"
read -r -d '' USAGE <<'EOF'
dirb.sh — web content / directory discovery

USAGE:
    dirb.sh <url> [wordlist]

Chooses the best installed engine, in order: ffuf > gobuster > dirsearch.
Default wordlist: proot SecLists common.txt, else a tiny built-in list.

EXAMPLES:
    dirb.sh http://target/
    dirb.sh http://target/ /path/to/wordlist.txt
EOF
andrax_usage_guard "$#"
andrax_init "$ANDRAX_TOOL_NAME"
url="$1"
wl="${2:-}"

# Pick a wordlist if none given.
if [ -z "$wl" ]; then
    for cand in \
        "$PREFIX/share/seclists/Discovery/Web-Content/common.txt" \
        "/data/data/com.termux/files/usr/share/wordlists/dirb/common.txt"; do
        [ -f "$cand" ] && wl="$cand" && break
    done
fi
if [ -z "$wl" ] || [ ! -f "$wl" ]; then
    wl="$(andrax_loot "mini-wordlist.txt")"
    printf '%s\n' admin login index.php robots.txt uploads backup config \
        .git .env api test dev wp-admin phpmyadmin server-status > "$wl"
    andrax_log "No SecLists found; using built-in mini wordlist ($wl)."
fi

out="$(andrax_loot "content.txt")"
if command -v ffuf >/dev/null 2>&1; then
    andrax_run ffuf -u "${url%/}/FUZZ" -w "$wl" -mc 200,204,301,302,307,401,403 -o "$out" -of csv
elif command -v gobuster >/dev/null 2>&1; then
    andrax_run gobuster dir -u "$url" -w "$wl" -o "$out"
elif command -v dirsearch >/dev/null 2>&1; then
    andrax_run dirsearch -u "$url" -w "$wl" --plain-text-report "$out"
else
    andrax_die "No content-discovery engine found. Run install_go_tools.sh (ffuf/gobuster) or install_python_tools.sh (dirsearch)."
fi
andrax_log "Saved to $out"
