#!/usr/bin/env bash
# ANDRAX 2.0 :: Wireless Attacks (limited) :: wifi_scan
# Modern Android cannot enter monitor mode / inject without special hardware.
# What IS realistic without root: enumerate nearby APs via the Android Wi-Fi
# stack (Termux:API) and analyse offline captures with aircrack-ng.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/toolkit.sh"
ANDRAX_TOOL_NAME="wifi_scan"
read -r -d '' USAGE <<'EOF'
wifi_scan.sh — realistic wireless recon on stock Android

USAGE:
    wifi_scan.sh scan                 # list nearby access points (Termux:API)
    wifi_scan.sh info                 # current connection info
    wifi_scan.sh crack <cap> <wl>     # offline WPA handshake crack (aircrack-ng)

LIMITATIONS: no monitor mode, no packet injection, no deauth on stock Android.
Use an external USB Wi-Fi adapter + root for those (out of scope here).
EOF
andrax_usage_guard "$#"
andrax_init "$ANDRAX_TOOL_NAME"
cmd="${1:-scan}"; shift || true
case "$cmd" in
    scan)
        andrax_need termux-wifi-scaninfo "pkg install termux-api (+ install the Termux:API app)"
        out="$(andrax_loot "wifi.json")"
        andrax_run termux-wifi-scaninfo | tee "$out" >/dev/null
        andrax_log "Access points saved to $out"
        ;;
    info)
        andrax_need termux-wifi-connectioninfo "pkg install termux-api"
        andrax_run termux-wifi-connectioninfo
        ;;
    crack)
        andrax_need aircrack-ng "pkg install aircrack-ng"
        cap="$1"; wl="$2"
        [ -f "$cap" ] || andrax_die "capture file '$cap' not found"
        [ -f "$wl" ]  || andrax_die "wordlist '$wl' not found"
        andrax_run aircrack-ng -w "$wl" "$cap"
        ;;
    *) printf '%s\n' "$USAGE"; exit 1 ;;
esac
