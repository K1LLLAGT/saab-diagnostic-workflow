"""
SAAB-SUITE — Ford OEM plugin (reference implementation).

Minimal second example demonstrating the same OEMPlugin contract as
plugins/gm, to show the plugin architecture is OEM-agnostic. Same
security-access caveat applies — see docs/security-access-disclaimer.md.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from src.plugins.base import OEMPlugin, VehicleInfo, RoutineResult, FlashBlock
from src.calibration.catalog import CalibrationCatalog


class Plugin(OEMPlugin):
    oem = "ford"
    protocols = ["ISO15765", "ISO9141"]
    min_year = 1998
    max_year = 2026

    def __init__(self) -> None:
        super().__init__()
        self.catalog = CalibrationCatalog()

    def initialize(self, vehicle_info: VehicleInfo) -> None:
        self.vehicle = vehicle_info

    def get_extended_pids(self) -> List[dict]:
        return [
            {"mode": "22", "pid": "4030", "name": "TRANS_FLUID_TEMP", "unit": "°C", "oem": "ford"},
            {"mode": "22", "pid": "404A", "name": "TURBO_BOOST_KPA", "unit": "kPa", "oem": "ford"},
        ]

    def decode_response(self, pid: int, data: bytes) -> Any:
        if pid == 0x4030:
            return data[0] - 40
        if pid == 0x404A:
            return round(int.from_bytes(data[:2], "big") * 0.1, 1)
        return int.from_bytes(data, "big") if data else None

    def run_routine(self, routine_id: int, params: Optional[bytes] = None) -> RoutineResult:
        return RoutineResult(routine_id, False, "No actuator routines registered in Ford reference plugin")

    def prepare_flash(self, cal_file: str) -> Dict[str, Any]:
        return {"ready": False, "reason": "Ford flash handler is a reference stub — not implemented"}

    def execute_flash(self, blocks: List[FlashBlock]) -> bool:
        raise NotImplementedError("Ford flash handler is a reference stub — not implemented")

    def recover_flash(self) -> bool:
        raise NotImplementedError("Ford flash handler is a reference stub — not implemented")

    def lookup_calibrations(self, vin: str) -> List[dict]:
        return [r.to_json() for r in self.catalog.lookup_by_vin(vin)]
