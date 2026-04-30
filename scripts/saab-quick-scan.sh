#!/usr/bin/env bash
set -euo pipefail

ROOTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGROOT="$ROOTDIR/logs"
TS="$(date +%Y%m%d-%H%M)"
RUNLOGDIR="$LOGROOT/quick-$TS"

mkdir -p "$RUNLOGDIR"

echo "[*] SAAB quick scan (CAN + basic diagnostics)"
echo "[*] Log directory: $RUNLOGDIR"

python3 -m src.can.bus --device j2534 --interface mongoose >> "$RUNLOGDIR/can-bus.log" 2>&1 || true
python3 "$ROOTDIR/scripts/diagnostic_scan.py" >> "$RUNLOGDIR/diagnostic-scan.log" 2>&1 || true

echo "[*] Quick scan complete. Logs in: $RUNLOGDIR"
