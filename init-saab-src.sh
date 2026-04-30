#!/usr/bin/env bash
set -euo pipefail

# Run from repo root
ROOTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[*] Scaffolding src/ package tree..."

mkdir -p \
  src/analysis \
  src/j2534 \
  src/can \
  src/uds \
  src/ecu \
  src/logging

##################################
# Top-level src/__init__.py
##################################
cat > src/__init__.py << 'EOF'
"""SAAB-SUITE — top-level package."""
EOF

##################################
# src/analysis/__init__.py
##################################
cat > src/analysis/__init__.py << 'EOF'
"""Analysis sub-package."""
EOF

##################################
# src/analysis/analyzer.py
##################################
cat > src/analysis/analyzer.py << 'EOF'
"""
SAAB-SUITE — Analysis module.

Entry point:  python3 -m src.analysis.analyzer
Responsibility: environment validation + diagnostic data analysis.
"""

import sys
import platform


def check_environment() -> bool:
    """Validate Python version and basic runtime environment."""
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 8):
        print(f"[!] Python 3.8+ required (found {major}.{minor})")
        return False
    print(f"[*] Python {major}.{minor}: OK")
    print(f"[*] Platform: {platform.system()} {platform.release()}")
    return True


def run() -> None:
    print("[*] src.analysis.analyzer — environment check")
    ok = check_environment()
    if not ok:
        sys.exit(1)
    print("[*] Analysis module ready.")


if __name__ == "__main__":
    run()
EOF

##################################
# src/j2534/__init__.py
##################################
cat > src/j2534/__init__.py << 'EOF'
"""J2534 pass-thru interface sub-package."""
EOF

##################################
# src/j2534/interface.py
##################################
cat > src/j2534/interface.py << 'EOF'
"""
SAAB-SUITE — J2534 interface module.

Entry point:  python3 -m src.j2534.interface --test
Hardware:     Mongoose Pro GM II (J2534 pass-thru)
"""

import sys
import argparse


def test_interface() -> bool:
    """
    Probe for a J2534 DLL / device.
    On Windows this checks the registry for installed J2534 devices.
    On Linux/Termux this checks for a CANUSB or FTDI device node.
    """
    import platform
    os_name = platform.system()

    if os_name == "Windows":
        return _test_windows()
    else:
        return _test_posix()


def _test_windows() -> bool:
    try:
        import winreg
        key_path = r"SOFTWARE\PassThruSupport.04.04"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            i = 0
            devices = []
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    devices.append(subkey_name)
                    i += 1
                except OSError:
                    break
        if devices:
            print(f"[*] J2534 devices found: {devices}")
            return True
        else:
            print("[!] No J2534 devices registered")
            return False
    except FileNotFoundError:
        print("[!] J2534 registry key not found (no J2534 driver installed?)")
        return False
    except ImportError:
        print("[!] winreg not available on this platform")
        return False


def _test_posix() -> bool:
    import os
    candidates = [
        "/dev/ttyUSB0",
        "/dev/ttyUSB1",
        "/dev/ttyACM0",
        "/dev/ttyACM1",
    ]
    found = [d for d in candidates if os.path.exists(d)]
    if found:
        print(f"[*] Serial/USB device(s) found: {found}")
        return True
    print("[!] No serial/USB device found for J2534 (Mongoose disconnected?)")
    return False


def run(args: argparse.Namespace) -> None:
    if args.test:
        print("[*] src.j2534.interface — interface probe")
        ok = test_interface()
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="J2534 interface probe")
    parser.add_argument("--test", action="store_true", help="Run interface self-test")
    args = parser.parse_args()
    run(args)
EOF

##################################
# src/can/__init__.py
##################################
cat > src/can/__init__.py << 'EOF'
"""CAN bus sub-package."""
EOF

##################################
# src/can/bus.py
##################################
cat > src/can/bus.py << 'EOF'
"""
SAAB-SUITE — CAN bus module.

Entry point:  python3 -m src.can.bus --device j2534 --interface mongoose
Supports:     J2534 pass-thru (Mongoose Pro GM II), CANUSB
"""

import sys
import argparse


SUPPORTED_DEVICES = ["j2534", "canusb", "socketcan"]
SUPPORTED_INTERFACES = ["mongoose", "canusb", "vcan0"]


def probe_can(device: str, interface: str) -> bool:
    print(f"[*] CAN probe — device={device}  interface={interface}")
    if device not in SUPPORTED_DEVICES:
        print(f"[!] Unknown device: {device}. Supported: {SUPPORTED_DEVICES}")
        return False
    if device == "j2534":
        print("[*] J2534 CAN channel: initialising...")
        print("[*] Protocol: ISO15765 / HS-CAN (500 kbps)")
        print("[!] CAN hardware not connected — stub mode")
        return True
    if device == "canusb":
        print("[*] CANUSB channel: initialising...")
        print("[!] CANUSB hardware not connected — stub mode")
        return True
    print(f"[!] Device '{device}' not yet implemented")
    return False


def run(args: argparse.Namespace) -> None:
    ok = probe_can(args.device, args.interface)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CAN bus probe")
    parser.add_argument("--device",    default="j2534",   help="Device type")
    parser.add_argument("--interface", default="mongoose", help="Interface name")
    args = parser.parse_args()
    run(args)
EOF

##################################
# src/uds/__init__.py  (stub)
##################################
cat > src/uds/__init__.py << 'EOF'
"""UDS (ISO 14229) sub-package — stub, Phase 3."""
EOF

cat > src/uds/client.py << 'EOF'
"""UDS client stub — Phase 3."""
EOF

##################################
# src/ecu/__init__.py  (stub)
##################################
cat > src/ecu/__init__.py << 'EOF'
"""ECU-specific sub-package (T8, ME9.6) — stub, Phase 3."""
EOF

cat > src/ecu/trionic8.py << 'EOF'
"""Trionic T8 ECU module stub — Phase 3."""
# Target: 2008 SAAB 9-3 XWD Aero / B284R / Trionic T8
EOF

##################################
# src/logging/__init__.py
##################################
cat > src/logging/__init__.py << 'EOF'
"""Structured logging sub-package."""
EOF

cat > src/logging/session.py << 'EOF'
"""
SAAB-SUITE — Session logger.

Creates a timestamped run directory and writes structured log entries.
"""

import os
import datetime
import pathlib


class SessionLogger:
    def __init__(self, root: str = "logs", prefix: str = "diag"):
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        self.run_dir = pathlib.Path(root) / f"{prefix}-{ts}"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self.run_dir / "session.log"
        self._write_header()

    def _write_header(self) -> None:
        with open(self._log_path, "w") as f:
            f.write(f"=== SAAB-SUITE SESSION LOG ===\n")
            f.write(f"Started: {datetime.datetime.now().isoformat()}\n\n")

    def log(self, msg: str) -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line)
        with open(self._log_path, "a") as f:
            f.write(line + "\n")

    @property
    def path(self) -> pathlib.Path:
        return self.run_dir
EOF

##################################
# scripts/diagnostic_scan.py
##################################
cat > scripts/diagnostic_scan.py << 'EOF'
#!/usr/bin/env python3
"""
SAAB-SUITE — Diagnostic scan script.

Called by saab-diagnostic-workflow.sh and saab-quick-scan.sh.
Orchestrates: analyzer → J2534 probe → CAN probe → session log.
"""

import sys
import pathlib

# Ensure repo root is on the path when called as a script
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from src.analysis.analyzer import check_environment
from src.j2534.interface import test_interface
from src.can.bus import probe_can
from src.logging.session import SessionLogger


def main() -> None:
    log = SessionLogger(prefix="scan")
    log.log("diagnostic_scan.py started")

    log.log("[1/3] Environment check...")
    if not check_environment():
        log.log("[!] Environment check failed")
        sys.exit(1)

    log.log("[2/3] J2534 interface probe...")
    j2534_ok = test_interface()
    if not j2534_ok:
        log.log("[!] J2534 probe failed — continuing in stub mode")

    log.log("[3/3] CAN bus probe...")
    can_ok = probe_can("j2534", "mongoose")
    if not can_ok:
        log.log("[!] CAN probe failed — continuing in stub mode")

    log.log(f"[*] Scan complete. Log: {log.path}")


if __name__ == "__main__":
    main()
EOF
chmod +x scripts/diagnostic_scan.py

echo ""
echo "[*] src/ scaffold complete."
echo "[*] Run:  ./saab doctor"
echo "[*] Then: git add -A && git commit -m 'feat: src/ package scaffold (Phase 2)'"

