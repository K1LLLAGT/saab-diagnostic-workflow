"""
SAAB-SUITE — flash-safe checklist engine.

Gates ECU programming behind a mandatory checklist. The flashing engine
(src/flashing/engine.py) refuses to start a write sequence unless
FlashSafeChecklist.all_clear() is True — see FlashSession.start() there.

Entry point:  python3 -m src.flashsafe.checklist --demo
"""

from __future__ import annotations
import argparse
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass
class CheckResult:
    name: str
    status: CheckStatus
    detail: str = ""


@dataclass
class VehicleState:
    """Snapshot of the conditions the checklist evaluates. Populate this
    from live telemetry (src.uds.client / src.pid.registry) before calling
    FlashSafeChecklist.evaluate()."""
    battery_voltage: Optional[float] = None
    ignition_on: Optional[bool] = None
    can_bus_stable: Optional[bool] = None          # e.g. no frame-loss / bus-off events
    j2534_buffer_ok: Optional[bool] = None          # tx/rx buffers not overrun
    programming_session_active: Optional[bool] = None
    blocking_dtcs: List[str] = field(default_factory=list)
    calibration_file_valid: Optional[bool] = None   # CVN / checksum verified against catalog


MIN_BATTERY_VOLTAGE = 12.4

# DTCs that must be absent before a flash may proceed (module-communication
# / voltage / programming-integrity codes). OEM plugins can extend this via
# OEMPlugin.blocking_dtc_codes().
DEFAULT_BLOCKING_DTC_PREFIXES = ("U", "P0562", "P0563", "P0601", "P0602", "P0603")


class FlashSafeChecklist:
    """
    Enforces:
      - Battery > 12.4V
      - Ignition ON
      - Stable CAN bus
      - No blocking DTCs
      - Correct calibration file (validated against the calibration catalog)
      - J2534 buffer validation
      - ECU programming session available
    """

    def __init__(self, blocking_dtc_prefixes: tuple = DEFAULT_BLOCKING_DTC_PREFIXES):
        self.blocking_dtc_prefixes = blocking_dtc_prefixes
        self.results: List[CheckResult] = []

    def evaluate(self, state: VehicleState) -> List[CheckResult]:
        self.results = [
            self._check_battery(state),
            self._check_ignition(state),
            self._check_bus_stability(state),
            self._check_j2534_buffer(state),
            self._check_programming_session(state),
            self._check_blocking_dtcs(state),
            self._check_calibration_file(state),
        ]
        return self.results

    def all_clear(self) -> bool:
        return bool(self.results) and all(r.status == CheckStatus.PASS for r in self.results)

    def failures(self) -> List[CheckResult]:
        return [r for r in self.results if r.status != CheckStatus.PASS]

    # ── Individual checks ────────────────────────────────────────────────

    def _check_battery(self, s: VehicleState) -> CheckResult:
        if s.battery_voltage is None:
            return CheckResult("battery_voltage", CheckStatus.UNKNOWN, "No voltage reading available")
        ok = s.battery_voltage > MIN_BATTERY_VOLTAGE
        return CheckResult(
            "battery_voltage",
            CheckStatus.PASS if ok else CheckStatus.FAIL,
            f"{s.battery_voltage:.2f} V (minimum {MIN_BATTERY_VOLTAGE} V)",
        )

    def _check_ignition(self, s: VehicleState) -> CheckResult:
        if s.ignition_on is None:
            return CheckResult("ignition_state", CheckStatus.UNKNOWN, "Ignition state not reported")
        return CheckResult("ignition_state", CheckStatus.PASS if s.ignition_on else CheckStatus.FAIL,
                            "ON" if s.ignition_on else "OFF — must be ON, engine may be running per OEM procedure")

    def _check_bus_stability(self, s: VehicleState) -> CheckResult:
        if s.can_bus_stable is None:
            return CheckResult("can_bus_stability", CheckStatus.UNKNOWN, "No bus health data")
        return CheckResult("can_bus_stability", CheckStatus.PASS if s.can_bus_stable else CheckStatus.FAIL,
                            "Stable" if s.can_bus_stable else "Bus errors / frame loss detected")

    def _check_j2534_buffer(self, s: VehicleState) -> CheckResult:
        if s.j2534_buffer_ok is None:
            return CheckResult("j2534_buffer", CheckStatus.UNKNOWN, "Buffer status not reported")
        return CheckResult("j2534_buffer", CheckStatus.PASS if s.j2534_buffer_ok else CheckStatus.FAIL,
                            "OK" if s.j2534_buffer_ok else "TX/RX buffer overrun detected")

    def _check_programming_session(self, s: VehicleState) -> CheckResult:
        if s.programming_session_active is None:
            return CheckResult("programming_session", CheckStatus.UNKNOWN, "Session state unknown")
        return CheckResult("programming_session", CheckStatus.PASS if s.programming_session_active else CheckStatus.FAIL,
                            "Active" if s.programming_session_active else "ECU did not accept programming session")

    def _check_blocking_dtcs(self, s: VehicleState) -> CheckResult:
        blockers = [
            code for code in s.blocking_dtcs
            if any(code.upper().startswith(p) for p in self.blocking_dtc_prefixes)
        ]
        if blockers:
            return CheckResult("blocking_dtcs", CheckStatus.FAIL, f"Blocking DTCs present: {', '.join(blockers)}")
        return CheckResult("blocking_dtcs", CheckStatus.PASS, "No blocking DTCs")

    def _check_calibration_file(self, s: VehicleState) -> CheckResult:
        if s.calibration_file_valid is None:
            return CheckResult("calibration_file", CheckStatus.UNKNOWN, "Calibration not yet validated against catalog")
        return CheckResult("calibration_file", CheckStatus.PASS if s.calibration_file_valid else CheckStatus.FAIL,
                            "Verified against calibration catalog" if s.calibration_file_valid
                            else "CVN/checksum mismatch or ECU/VIN application mismatch")


def _demo() -> None:
    good = VehicleState(
        battery_voltage=13.1, ignition_on=True, can_bus_stable=True,
        j2534_buffer_ok=True, programming_session_active=True,
        blocking_dtcs=[], calibration_file_valid=True,
    )
    checklist = FlashSafeChecklist()
    for r in checklist.evaluate(good):
        print(f"  [{r.status.value:7s}] {r.name:24s} {r.detail}")
    print(f"\nAll clear: {checklist.all_clear()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flash-safe checklist engine")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    if args.demo:
        _demo()
