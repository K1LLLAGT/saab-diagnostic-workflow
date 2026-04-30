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
