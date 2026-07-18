#!/usr/bin/env bash
# ANDRAX 2.0 :: Information Gathering :: dnsenum
# DNS enumeration using dig (dnsutils) + optional subfinder for subdomains.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/toolkit.sh"
ANDRAX_TOOL_NAME="dnsenum"
read -r -d '' USAGE <<'EOF'
dnsenum.sh — DNS record + subdomain enumeration

USAGE:
    dnsenum.sh <domain>

WHAT IT DOES:
    * Resolves A / AAAA / MX / NS / TXT / SOA records via dig
    * If 'subfinder' (go tool) is installed, enumerates subdomains passively

EXAMPLE:
    dnsenum.sh example.com
EOF
andrax_usage_guard "$#"
andrax_init "$ANDRAX_TOOL_NAME"
andrax_need dig "pkg install dnsutils"
domain="$1"
out="$(andrax_loot "dns.txt")"

for rr in A AAAA MX NS TXT SOA CNAME; do
    andrax_log "--- $rr records for $domain ---"
    andrax_run dig +short "$domain" "$rr" | tee -a "$out"
done

if command -v subfinder >/dev/null 2>&1; then
    andrax_log "--- passive subdomain enumeration (subfinder) ---"
    andrax_run subfinder -silent -d "$domain" | tee -a "$out"
else
    andrax_log "subfinder not installed (run install_go_tools.sh) — skipping subdomains."
fi
andrax_log "Saved to $out"
