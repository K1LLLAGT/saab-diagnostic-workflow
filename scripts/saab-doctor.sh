#!/usr/bin/env bash
set -euo pipefail

ROOTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[*] SAAB-SUITE environment self-test (saab doctor)"

echo "[1/5] Checking Python..."
command -v python3 >/dev/null || { echo "[!] python3 not found"; exit 1; }
echo "    python3: OK"

echo "[2/5] Checking core Python modules..."
python3 - << 'PYEOF'
import importlib, sys
mods = ["src.analysis.analyzer", "src.j2534.interface", "src.can.bus"]
failed = []
for m in mods:
    try:
        importlib.import_module(m)
    except Exception as e:
        failed.append((m, str(e)))
if failed:
    print("[!] Missing/broken modules:")
    for m, e in failed:
        print("   -", m, "->", e)
    sys.exit(1)
print("[*] Core modules import: OK")
PYEOF

echo "[3/5] Checking docs..."
for f in \
  "docs/saab-diagnostic-workflow.md" \
  "docs/workflows/saab-9-3-aero-xwd.md" \
  "docs/module-programming-matrix.md" \
  "docs/architecture.md"; do
  [ -f "$ROOTDIR/$f" ] || { echo "[!] Missing doc: $f"; exit 1; }
done
echo "    Documentation: OK"

echo "[4/5] Checking scripts..."
for f in \
  "scripts/saab-diagnostic-workflow.sh" \
  "scripts/saab-quick-scan.sh" \
  "scripts/saab-doctor.sh"; do
  [ -x "$ROOTDIR/$f" ] || { echo "[!] Script missing or not executable: $f"; exit 1; }
done
echo "    Scripts: OK"

echo "[5/5] Optional J2534 test..."
python3 -m src.j2534.interface --test >/dev/null 2>&1 \
  && echo "    J2534 / Mongoose: OK" \
  || echo "    [!] J2534 test failed (interface may be disconnected)"

echo "[*] saab doctor completed."
