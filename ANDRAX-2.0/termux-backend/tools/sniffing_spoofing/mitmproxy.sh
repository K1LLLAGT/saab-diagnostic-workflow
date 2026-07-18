#!/usr/bin/env bash
# ANDRAX 2.0 :: Sniffing & Spoofing :: mitmproxy
# On stock Android, ARP spoofing / ettercap need raw sockets (root). The
# realistic user-space equivalent is an application-layer intercepting proxy
# the user points a device/app at. That's mitmproxy.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/toolkit.sh"
ANDRAX_TOOL_NAME="mitmproxy"
read -r -d '' USAGE <<'EOF'
mitmproxy.sh — application-layer intercepting proxy (ettercap replacement)

USAGE:
    mitmproxy.sh [start|web|dump] [extra args...]

MODES:
    start   interactive TUI proxy on :8080 (default)
    web     mitmweb browser UI on :8081
    dump    headless mitmdump, logs flows to loot

SETUP: point the target device/app HTTP(S) proxy at THIS device's IP:8080 and
install the mitmproxy CA cert on the target (http://mitm.it). This is a
consented MITM for testing your own traffic — no raw packet injection needed.
EOF
andrax_usage_guard "$#"
andrax_init "$ANDRAX_TOOL_NAME"
andrax_need mitmproxy "pip install mitmproxy (install_python_tools.sh)"
mode="${1:-start}"; shift || true
case "$mode" in
    start) andrax_run mitmproxy --listen-port 8080 "$@" ;;
    web)   andrax_run mitmweb --listen-port 8080 --web-port 8081 "$@" ;;
    dump)  out="$(andrax_loot "flows.log")"
           andrax_run mitmdump --listen-port 8080 -w "$out" "$@" ;;
    *)     printf '%s\n' "$USAGE"; exit 1 ;;
esac
