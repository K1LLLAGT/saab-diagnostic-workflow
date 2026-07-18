#!/usr/bin/env bash
# ANDRAX 2.0 — install base Termux packages and core security tools.
# Idempotent: safe to run multiple times.
set -euo pipefail

echo "[andrax-setup] Updating package lists..."
pkg update -y
pkg upgrade -y

# --- base runtime ----------------------------------------------------------
BASE_PKGS=(
    bash coreutils grep sed gawk findutils procps
    git curl wget openssh jq                  # plumbing
    python python-pip                          # python tools
    golang                                     # go tools (optional installers)
    rust                                       # rust tools (optional installers)
    ruby                                       # wpscan / misc gems
    proot proot-distro                         # userland layer
    termux-api                                 # app<->backend bridge, wifi info
    ncurses-utils                              # tput for the menus
)

# --- core security tools available as Termux packages ----------------------
SEC_PKGS=(
    nmap                    # network scanning
    whois                  # whois lookups
    dnsutils               # dig / nslookup
    hydra                  # online password attacks
    john                   # offline password cracking
    nikto                  # web server scanner
    sqlmap                 # sql injection
    metasploit             # exploitation framework (large!)
    binwalk                # firmware/forensics
    tcpdump                # packet capture (limited without root)
    netcat-openbsd         # swiss-army networking
    hashcat                # hashing (CPU on-device)
    aircrack-ng            # wifi crypto (offline capture analysis)
    tsu                    # su wrapper for rooted devices (no-op otherwise)
)

echo "[andrax-setup] Installing base packages..."
pkg install -y "${BASE_PKGS[@]}"

echo "[andrax-setup] Installing core security packages (metasploit is large)..."
# Install individually so one failure doesn't abort the whole batch.
for p in "${SEC_PKGS[@]}"; do
    echo "  -> $p"
    pkg install -y "$p" || echo "     [warn] '$p' not available in this repo; skipping"
done

echo "[andrax-setup] Enabling app<->Termux bridge (allow-external-apps)..."
mkdir -p "$HOME/.termux"
if ! grep -q '^allow-external-apps=true' "$HOME/.termux/termux.properties" 2>/dev/null; then
    echo 'allow-external-apps=true' >> "$HOME/.termux/termux.properties"
fi
command -v termux-reload-settings >/dev/null 2>&1 && termux-reload-settings || true

echo "[andrax-setup] Base Termux backend installed."
echo "[andrax-setup] Next: install_python_tools.sh  (and optionally setup_proot_kali.sh)"
