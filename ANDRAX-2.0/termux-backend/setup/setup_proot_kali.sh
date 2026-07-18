#!/usr/bin/env bash
# ANDRAX 2.0 — optional Kali/Debian userland via proot-distro.
# This gives you tools not packaged for Termux (wpscan, full msf module set,
# enum4linux, etc.) inside an unprivileged user-space Linux rootfs. No root,
# no chroot, no loop mounts — pure proot syscall emulation.
set -euo pipefail

DISTRO="${1:-kali}"     # kali | debian | archlinux | ubuntu

command -v proot-distro >/dev/null 2>&1 || pkg install -y proot-distro

echo "[andrax-setup] Installing proot userland: $DISTRO"
proot-distro list | grep -q "$DISTRO" && proot-distro install "$DISTRO" || \
    echo "[andrax-setup] '$DISTRO' already installed or install skipped"

echo "[andrax-setup] Provisioning tools inside $DISTRO ..."
proot-distro login "$DISTRO" -- bash -c '
    set -e
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y --no-install-recommends \
        wpscan enum4linux smbclient dnsrecon whatweb \
        seclists wordlists curl git ruby || true
    echo "[proot] userland provisioning complete"
'

echo "[andrax-setup] Done. Enter the userland any time with:"
echo "    proot-distro login $DISTRO"
echo "[andrax-setup] ANDRAX tool wrappers call it automatically via andrax_proot."
