#!/usr/bin/env bash
set -euo pipefail

ROOTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGROOT="$ROOTDIR/logs"
TS="$(date +%Y%m%d-%H%M)"
RUNLOGDIR="$LOGROOT/diag-$TS"

mkdir -p "$RUNLOGDIR"

echo "[*] SAAB-SUITE diagnostic workflow launcher"
echo "[*] Log directory: $RUNLOGDIR"

{
  echo "=== SAAB DIAGNOSTIC WORKFLOW RUN ==="
  echo "Timestamp: $(date -Iseconds)"
  echo "PWD: $ROOTDIR"
  echo "Command: $0 $*"
  echo
} > "$RUNLOGDIR/run-info.txt"

python3 -m src.analysis.analyzer >> "$RUNLOGDIR/analyzer.log" 2>&1 || {
  echo "[!] Python environment check failed"
  exit 1
}

python3 -m src.j2534.interface --test >> "$RUNLOGDIR/j2534-test.log" 2>&1 || {
  echo "[!] J2534 / Mongoose test failed"
  exit 1
}

python3 "$ROOTDIR/scripts/diagnostic_scan.py" >> "$RUNLOGDIR/diagnostic-scan.log" 2>&1 || {
  echo "[!] Diagnostic scan encountered errors"
  exit 1
}

echo "[*] Workflow completed. Logs in: $RUNLOGDIR"
