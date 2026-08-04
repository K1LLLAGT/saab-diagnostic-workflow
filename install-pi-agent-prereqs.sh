#!/usr/bin/env bash
set -euo pipefail

# Minimal Pi 5 prerequisites for the capture/agent (socketcan + python libs).
# Run on Raspberry Pi OS (64-bit Bookworm) as root or with sudo.

echo "[*] Updating apt and installing system packages..."
sudo apt update
sudo apt install -y python3-pip can-utils git

echo "[*] Upgrading pip..."
python3 -m pip install --upgrade pip

echo "[*] Installing Python packages for the Pi capture agent..."
python3 -m pip install python-can cantools pyserial

# Optional (recommended for archive sync / admin tasks):
# sudo apt install -y rclone

# Notes / next manual steps:
cat <<'EOF'

Next manual steps (one-time):
- Enable SPI + MCP2515 overlay so the HAT works. Edit /boot/firmware/config.txt
  and add (or verify) these lines:
    dtparam=spi=on
    dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=25
    dtoverlay=spi-bcm2835

  If your system uses /boot/config.txt instead of /boot/firmware/config.txt,
  edit that file instead.

- Bring up the SocketCAN interface (replace can0 if your device uses another name):
    sudo ip link set can0 up type can bitrate 500000

- Verify with candump / can-utils:
    candump can0

EOF

echo "[*] Done. Installed: python-can, cantools, pyserial; system pkgs: python3-pip, can-utils."
