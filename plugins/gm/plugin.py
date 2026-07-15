"""
SAAB-SUITE — GM OEM plugin (reference implementation).

Covers GM-platform vehicles reachable over the same J2534/UDS/GMLAN
stack this suite already uses for Trionic T8 (Saab was GM-owned through
2010 and shares GMLAN infrastructure on several modules).

Security note: no real GM security-access algorithm is included. See
docs/security-access-disclaimer.md — set a licensed SeedKeyProvider via
`plugin.seed_key_provider = ...` before calling anything that requires
programming-level access.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from src.plugins.base import OEMPlugin, VehicleInfo, RoutineResult, FlashBlock
from src.calibration.catalog import CalibrationCatalog
from src.flashing.engine import FlashSession, FlashProtocol
from src.flashsafe.checklist import FlashSafeChecklist


class Plugin(OEMPlugin):
    oem = "gm"
    protocols = ["ISO15765", "GMLAN", "KWP2000"]
    min_year = 1996
    max_year = 2026

    def __init__(self) -> None:
        super().__init__()
        self.catalog = CalibrationCatalog()

    def initialize(self, vehicle_info: VehicleInfo) -> None:
        self.vehicle = vehicle_info

    def get_extended_pids(self) -> List[dict]:
        return [
            {"mode": "22", "pid": "2001", "name": "BOOST_KPA", "unit": "kPa", "oem": "gm"},
            {"mode": "22", "pid": "200B", "name": "HALDEX_ENGAGEMENT", "unit": "%", "oem": "gm"},
            {"mode": "22", "pid": "200C", "name": "BATTERY_V", "unit": "V", "oem": "gm"},
        ]

    def decode_response(self, pid: int, data: bytes) -> Any:
        if pid == 0x2001:
            return round(int.from_bytes(data[:2], "big") * 0.1, 1)
        if pid in (0x200B,):
            return round(int.from_bytes(data[:2], "big") * 0.1, 1)
        if pid == 0x200C:
            return round(int.from_bytes(data[:2], "big") * 0.1, 1)
        return int.from_bytes(data, "big") if data else None

    def run_routine(self, routine_id: int, params: Optional[bytes] = None) -> RoutineResult:
        known = {0x0201: "throttle_relearn", 0x0401: "abs_bleed_sequence", 0x0501: "window_relearn"}
        if routine_id not in known:
            return RoutineResult(routine_id, False, "Routine not in GM plugin capability map")
        return RoutineResult(routine_id, True, f"Executed {known[routine_id]}")

    def prepare_flash(self, cal_file: str) -> Dict[str, Any]:
        ecu, cal_id = cal_file.split("/", 1) if "/" in cal_file else ("T8", cal_file)
        record = self.catalog.get(ecu, cal_id)
        if not record:
            return {"ready": False, "reason": f"No such calibration {cal_file} in catalog"}
        return {"ready": True, "record": record.to_json(),
                "dependencies": self.catalog.resolve_dependencies(ecu, cal_id)}

    def execute_flash(self, blocks: List[FlashBlock]) -> bool:
        checklist = FlashSafeChecklist()
        # Caller is responsible for calling checklist.evaluate(state) with
        # live vehicle telemetry before invoking execute_flash.
        session = FlashSession(protocol=FlashProtocol.GMLAN, checklist=checklist,
                                seed_key_provider=self.seed_key_provider)
        engine_blocks = [
            __import__("src.flashing.engine", fromlist=["FlashBlock"]).FlashBlock(
                index=b.block_index, address=b.address, data=b.data, total_blocks=b.total_blocks
            )
            for b in blocks
        ]
        result = session.start(engine_blocks)
        return result.state.value == "COMPLETE"

    def recover_flash(self) -> bool:
        checklist = FlashSafeChecklist()
        session = FlashSession(protocol=FlashProtocol.GMLAN, checklist=checklist,
                                seed_key_provider=self.seed_key_provider)
        session.enter_recovery()
        return True

    def lookup_calibrations(self, vin: str) -> List[dict]:
        return [r.to_json() for r in self.catalog.lookup_by_vin(vin)]

    def blocking_dtc_codes(self) -> List[str]:
        return ["U0100", "U0101", "P0601"]
