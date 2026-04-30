#!/usr/bin/env bash
set -euo pipefail

echo "[*] Initializing SAAB-SUITE workflow stack (canonical version)..."

mkdir -p docs docs/workflows docs/installation scripts bin logs

##################################
# 1) Top-level README with badges
##################################
cat > README.md << 'EOF'
# SAAB Diagnostic Workflow Suite

![Status](https://img.shields.io/badge/status-active-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)
![Platform](https://img.shields.io/badge/platform-Win7--SAAB%20VM-lightgrey)
![Interface](https://img.shields.io/badge/interface-Mongoose%20Pro%20GM%20II-orange)

A complete, technician-grade diagnostic workflow for SAAB vehicles using:

- Mongoose Pro GM II (J2534)
- Win7-SAAB VM (VMware Workstation Pro)
- GlobalTIS SPS
- GDS2
- TIS2000
- SAAB-SUITE automation scripts

---

## Quick start

```bash
./saab workflow      # Full guided diagnostic workflow
./saab quick-scan    # Fast CAN + DTC scan
./saab doctor        # Environment self-test
```

---

## Documentation

- [Diagnostic Workflow](docs/saab-diagnostic-workflow.md)
- [9-3 Aero XWD Workflow](docs/workflows/saab-9-3-aero-xwd.md)
- [Module Programming Matrix](docs/module-programming-matrix.md)
- [Architecture](docs/architecture.md)

---

## Logging

All diagnostic runs are logged under:

```
logs/diag-YYYYMMDD-HHMM/
```

Each run captures:

- Command line used
- Basic environment snapshot
- Tool output

---

## Philosophy

Deterministic, reproducible, technician-friendly.
Clone → Follow docs → Run `./saab workflow` → Get consistent results.
EOF

##################################
# 2) GitHub Pages entry: docs/index.md
##################################
cat > docs/index.md << 'EOF'
# SAAB Diagnostic Workflow Suite

Welcome to the SAAB-SUITE diagnostic workflow stack.

This site mirrors the core repo documentation and is intended as a technician-friendly reference.

---

## Core documents

- [Diagnostic Workflow](saab-diagnostic-workflow.md)
- [9-3 Aero XWD Workflow](workflows/saab-9-3-aero-xwd.md)
- [Module Programming Matrix](module-programming-matrix.md)
- [Architecture](architecture.md)

---

## Entry points

```bash
./saab workflow
./saab quick-scan
./saab doctor
```
EOF

##################################
# 3) SAAB-SUITE architecture diagram
##################################
cat > docs/architecture.md << 'EOF'
# SAAB-SUITE Architecture

This document shows how the pieces fit together: hardware, VM, OEM tools, and SAAB-SUITE scripts.

---

## High-level diagram

```text
+-----------------------------+
|        Technician           |
+--------------+--------------+
               |
               v
+-----------------------------+
|        SAAB CLI (./saab)    |
|  - workflow                 |
|  - quick-scan               |
|  - doctor                   |
+--------------+--------------+
               |
               v
+-----------------------------+
|       SAAB-SUITE Scripts    |
|  - scripts/saab-diagnostic- |
|    workflow.sh              |
|  - scripts/saab-quick-scan.sh|
|  - src/* (CAN, UDS, J2534)  |
+--------------+--------------+
               |
               v
+-----------------------------+
|      Win7-SAAB VM           |
|  - GlobalTIS SPS            |
|  - GDS2                     |
|  - TIS2000                  |
|  - J2534 Toolbox 3          |
+--------------+--------------+
               |
               v
+-----------------------------+
|   Mongoose Pro GM II (USB)  |
+--------------+--------------+
               |
               v
+-----------------------------+
|       SAAB Vehicle (OBD-II) |
+-----------------------------+
```
EOF

##################################
# 4) Diagnostic workflow script (with logging)
##################################
cat > scripts/saab-diagnostic-workflow.sh << 'EOF'
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
EOF
chmod +x scripts/saab-diagnostic-workflow.sh

##################################
# 5) Quick scan script
##################################
cat > scripts/saab-quick-scan.sh << 'EOF'
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
EOF
chmod +x scripts/saab-quick-scan.sh

##################################
# 6) Self-test command: saab doctor
##################################
cat > scripts/saab-doctor.sh << 'EOF'
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
EOF
chmod +x scripts/saab-doctor.sh

##################################
# 7) SAAB CLI wrapper
##################################
cat > saab << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

ROOTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CMD="${1:-help}"
shift || true

case "$CMD" in
  workflow)
    "$ROOTDIR/scripts/saab-diagnostic-workflow.sh" "$@"
    ;;
  quick-scan|quick)
    "$ROOTDIR/scripts/saab-quick-scan.sh" "$@"
    ;;
  doctor)
    "$ROOTDIR/scripts/saab-doctor.sh" "$@"
    ;;
  help|--help|-h)
    cat << 'USAGE'
SAAB-SUITE CLI

Usage:
  ./saab workflow        Run full diagnostic workflow
  ./saab quick-scan      Run quick CAN + DTC scan
  ./saab doctor          Run environment self-test
USAGE
    ;;
  *)
    echo "[!] Unknown command: $CMD"
    echo "    Try: ./saab help"
    exit 1
    ;;
esac
EOF
chmod +x saab

echo "[*] Canonical SAAB-SUITE stack initialized."
echo "[*] Commit and push to GitHub, then enable GitHub Pages (docs/)."

