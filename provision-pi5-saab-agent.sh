#!/usr/bin/env bash
# Provisioning script for Raspberry Pi 5 — installs Pi capture agent runtime,
# configures MCP2515/socketcan dtoverlay, creates venv, and enables a systemd
# service to run the agent.
#
# Usage:
#   sudo ./provision-pi5-saab-agent.sh
#
# Defaults:
#   INSTALL_DIR=/opt/saabpi
#   GIT_REPO=https://github.com/K1LLLAGT/saab-diagnostic-workflow.git
#   RUN_AS_USER = SUDO_USER if run with sudo, else current $USER
#
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

# -------- Configuration --------
INSTALL_DIR=${INSTALL_DIR:-/opt/saabpi}
GIT_REPO=${GIT_REPO:-https://github.com/K1LLLAGT/saab-diagnostic-workflow.git}
APP_DIR="$INSTALL_DIR/app"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_NAME="saab-pi-agent"
BOOT_CFG_CANDIDATES=(/boot/firmware/config.txt /boot/config.txt)
# pip packages for the Pi capture agent (extend if needed)
PIP_PKGS=(python-can cantools pyserial httpx websockets)
# dtoverlay lines to ensure
DT_PARAM_SPI="dtparam=spi=on"
DTO_MCP="dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=25"
DTO_SPI_BCM="dtoverlay=spi-bcm2835"
# -------------------------------

if [ "$(id -u)" -ne 0 ]; then
  echo "[!] This script must be run as root (sudo). Re-run using sudo."
  exit 1
fi

# Determine the non-root user to run the service as
if [ -n "${SUDO_USER:-}" ] && [ "${SUDO_USER}" != "root" ]; then
  RUN_AS_USER="$SUDO_USER"
else
  # fallback to environment user
  RUN_AS_USER="${RUN_AS_USER:-${USER:-pi}}"
fi
echo "[*] Service will run as user: $RUN_AS_USER"

echo "[*] Updating apt and installing system packages..."
apt update -y
apt install -y python3-venv python3-pip can-utils git

# Create install dir and set ownership
if [ ! -d "$INSTALL_DIR" ]; then
  mkdir -p "$INSTALL_DIR"
  chown "$RUN_AS_USER":"$RUN_AS_USER" "$INSTALL_DIR"
  chmod 755 "$INSTALL_DIR"
  echo "[*] Created $INSTALL_DIR"
fi

# Clone or update repository
if [ ! -d "$APP_DIR/.git" ]; then
  echo "[*] Cloning repo $GIT_REPO into $APP_DIR..."
  sudo -u "$RUN_AS_USER" git clone --depth=1 "$GIT_REPO" "$APP_DIR"
else
  echo "[*] Repo already exists in $APP_DIR — fetching latest..."
  pushd "$APP_DIR" > /dev/null
  sudo -u "$RUN_AS_USER" git fetch --depth=1 origin
  sudo -u "$RUN_AS_USER" git reset --hard origin/$(git rev-parse --abbrev-ref HEAD || echo main)
  popd > /dev/null
fi

# Create virtualenv if missing
if [ ! -d "$VENV_DIR" ]; then
  echo "[*] Creating virtualenv at $VENV_DIR..."
  python3 -m venv "$VENV_DIR"
  chown -R "$RUN_AS_USER":"$RUN_AS_USER" "$VENV_DIR"
fi

# Install pip packages into venv
echo "[*] Installing pip packages into venv: ${PIP_PKGS[*]} ..."
# Use pip inside venv
"${VENV_DIR}/bin/python" -m pip install --upgrade pip setuptools wheel
for pkg in "${PIP_PKGS[@]}"; do
  "${VENV_DIR}/bin/python" -m pip install --upgrade "$pkg"
done

# Idempotent dtoverlay configuration: add required lines to boot config if missing
BOOT_CFG=""
for candidate in "${BOOT_CFG_CANDIDATES[@]}"; do
  if [ -f "$candidate" ]; then
    BOOT_CFG="$candidate"
    break
  fi
done

if [ -z "$BOOT_CFG" ]; then
  echo "[!] Could not find /boot/firmware/config.txt or /boot/config.txt. Skipping dtoverlay step."
else
  echo "[*] Ensuring dtoverlay/SPi lines exist in $BOOT_CFG"
  # Backup config first (idempotent: only create if missing)
  BACKUP="${BOOT_CFG}.saab.bak"
  if [ ! -f "$BACKUP" ]; then
    cp "$BOOT_CFG" "$BACKUP"
    echo "[*] Backed up $BOOT_CFG → $BACKUP"
  fi

  # Add each required line if not present (simple grep-based check)
  grep -qxF "$DT_PARAM_SPI" "$BOOT_CFG" || echo "$DT_PARAM_SPI" >> "$BOOT_CFG"
  grep -qxF "$DTO_MCP" "$BOOT_CFG" || echo "$DTO_MCP" >> "$BOOT_CFG"
  grep -qxF "$DTO_SPI_BCM" "$BOOT_CFG" || echo "$DTO_SPI_BCM" >> "$BOOT_CFG"

  echo "[*] dtoverlay lines ensured in $BOOT_CFG (a reboot may be required for overlays to load)."
fi

# Try to bring up can0 (if kernel driver created the device)
if ip link show can0 > /dev/null 2>&1; then
  echo "[*] Bringing up can0 with 500000 bitrate..."
  ip link set can0 up type can bitrate 500000 || {
    echo "[!] ip link set can0 failed — ensure your MCP2515/CAN HAT is present and drivers loaded."
  }
  echo "[*] If can0 is up, verify with: ip -details link show can0"
else
  echo "[*] No can0 interface present (yet). It will appear after a reboot if dtoverlay loaded and HAT is attached."
fi

# Create a simple wrapper entrypoint script in the app directory that the service will run.
ENTRYPOINT="$APP_DIR/run_pi_agent.sh"
cat > "$ENTRYPOINT" <<'EOF'
#!/usr/bin/env bash
# Wrapper to run the Pi agent inside the project's venv.
# Behavior:
# - If a top-level pi_agent.py exists in the repo, run it.
# - Otherwise, fall back to running the sniffer demo (safe default).
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${VENV_DIR_OVERRIDE:-/opt/saabpi/venv}"

# Activate venv
export PATH="$VENV_DIR/bin:$PATH"

cd "$APP_DIR"

if [ -x "$APP_DIR/pi_agent.py" ]; then
  echo "[*] Starting pi_agent.py"
  exec python3 "$APP_DIR/pi_agent.py" "$@"
else
  echo "[*] No pi_agent.py found — running sniffer demo as safe default"
  exec python3 -m src.sniffer.engine --demo
fi
EOF
chmod 755 "$ENTRYPOINT"
chown "$RUN_AS_USER":"$RUN_AS_USER" "$ENTRYPOINT"
echo "[*] Created wrapper entrypoint at $ENTRYPOINT"

# Create systemd service unit
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=SAAB Pi capture agent
After=network.target

[Service]
Type=simple
User=${RUN_AS_USER}
Group=${RUN_AS_USER}
WorkingDirectory=${APP_DIR}
Environment=VENV_DIR_OVERRIDE=${VENV_DIR}
ExecStart=${ENTRYPOINT}
Restart=on-failure
RestartSec=5
# Protect system a bit:
NoNewPrivileges=true
ProtectSystem=full

[Install]
WantedBy=multi-user.target
EOF

echo "[*] Installed systemd unit: $SERVICE_FILE"

# Reload systemd, enable and start service
systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}.service"

echo
echo "[*] Done. Service ${SERVICE_NAME} enabled and started (status below)."
systemctl status --no-pager "${SERVICE_NAME}.service" || true

cat <<'EOF'

Notes & next steps:
- A reboot may be required to apply dtoverlay changes (if /boot config was edited).
- The service will attempt to run:
    - ${APP_DIR}/pi_agent.py (if present and executable), else
    - python -m src.sniffer.engine --demo
  Replace the wrapper's behavior by adding ${APP_DIR}/pi_agent.py or editing ${ENTRYPOINT}.
- If you prefer the service to run a different module, update /etc/systemd/system/${SERVICE_NAME}.service
  ExecStart line and run: sudo systemctl daemon-reload && sudo systemctl restart ${SERVICE_NAME}
- To inspect logs:
    sudo journalctl -u ${SERVICE_NAME}.service -f

EOF
