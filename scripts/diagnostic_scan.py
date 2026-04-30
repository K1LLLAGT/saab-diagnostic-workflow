#!/usr/bin/env python3
"""
SAAB-SUITE — Diagnostic scan script (Phase 3).

Orchestrates: analyzer → J2534 probe → CAN probe → T8 live data
All output tagged to VIN and written to structured JSON session log.
"""

import sys
import argparse
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from src.analysis.analyzer   import check_environment
from src.j2534.interface     import test_interface
from src.can.bus             import probe_can
from src.ecu.trionic8        import Trionic8
from src.logging.session     import SessionLogger

# ── Default VIN: 2008 SAAB 9-3 XWD Aero ──────────────────────────────────
DEFAULT_VIN = "YS3FD45Y381234567"


def main() -> None:
    parser = argparse.ArgumentParser(description="SAAB-SUITE diagnostic scan")
    parser.add_argument("--vin",  default=DEFAULT_VIN, help="Vehicle VIN")
    parser.add_argument("--stub", action="store_true",  default=True,
                        help="Stub mode (no hardware required)")
    args = parser.parse_args()

    log = SessionLogger(vin=args.vin, prefix="scan")
    log.info(f"diagnostic_scan.py started  vin={args.vin}  stub={args.stub}")

    # [1/4] Environment
    log.info("[1/4] Environment check...")
    if not check_environment():
        log.error("Environment check failed")
        sys.exit(1)
    log.info("Environment: OK")

    # [2/4] J2534
    log.info("[2/4] J2534 interface probe...")
    j2534_ok = test_interface()
    if j2534_ok:
        log.info("J2534 / Mongoose: OK")
    else:
        log.warning("J2534 not found — continuing in stub mode")

    # [3/4] CAN
    log.info("[3/4] CAN bus probe...")
    can_ok = probe_can("j2534", "mongoose")
    if can_ok:
        log.info("CAN bus: OK")
    else:
        log.warning("CAN probe failed — stub mode")

    # [4/4] T8 live data
    log.info("[4/4] Trionic T8 ECU read...")
    t8 = Trionic8(stub=args.stub)
    t8.connect()

    info = t8.read_ecu_info()
    for k, v in info.items():
        log.data(k, v)

    live = t8.read_live_data()
    log.data("RPM",           live.rpm)
    log.data("BOOST_KPA",     live.boost_kpa)
    log.data("COOLANT_C",     live.coolant_c)
    log.data("IAT_C",         live.iat_c)
    log.data("THROTTLE_PCT",  live.throttle_pct)
    log.data("IGN_TIMING",    live.ign_timing)
    log.data("LAMBDA",        live.lambda_)
    log.data("KNOCK_RETARD",  live.knock_retard)
    log.data("WASTEGATE",     live.wastegate_duty)
    log.data("HALDEX",        live.haldex_engagement)
    log.data("BATTERY_V",     live.battery_v)
    log.data("SPEED",         live.vehicle_speed)
    log.data("MAF_GS",        live.maf_gs)
    log.data("FUEL_TRIM_ST",  live.fuel_trim_st)
    log.data("FUEL_TRIM_LT",  live.fuel_trim_lt)

    dtc_raw = t8.read_dtcs()
    dtc_count = max(0, (len(dtc_raw) - 1) // 3)
    log.data("DTC_COUNT", dtc_count)

    t8.disconnect()

    log.finalize(dtc_count=dtc_count)
    print(f"\n[*] Session log: {log.json_path}")


if __name__ == "__main__":
    main()
