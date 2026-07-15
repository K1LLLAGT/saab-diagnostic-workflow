"""
SAAB-SUITE — PID registry.

Standard SAE J1979 OBD-II PIDs (Modes 01/02/03/04/09) plus a hook for
OEM extended PIDs contributed by plugins (see src/plugins/base.py).

Entry point:  python3 -m src.pid.registry --list --mode 01
"""

from __future__ import annotations
import argparse
import json
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


# ── Modes ─────────────────────────────────────────────────────────────────

class Mode:
    CURRENT_DATA   = 0x01
    FREEZE_FRAME   = 0x02
    STORED_DTC     = 0x03
    CLEAR_DTC      = 0x04
    OXYGEN_MONITOR = 0x05
    ON_BOARD_MONITOR = 0x06
    PENDING_DTC    = 0x07
    CONTROL        = 0x08
    VEHICLE_INFO   = 0x09
    PERMANENT_DTC  = 0x0A


@dataclass
class PIDDefinition:
    mode: int
    pid: int
    name: str
    description: str
    bytes_expected: int
    unit: str = ""
    decode: Optional[Callable[[bytes], float | int | str]] = None
    min_hz: float = 1.0
    max_hz: float = 50.0
    oem: Optional[str] = None   # None = standard SAE J1979 PID; else plugin OEM tag

    def decode_value(self, data: bytes):
        if self.decode:
            return self.decode(data)
        if len(data) == 1:
            return data[0]
        if len(data) >= 2:
            return int.from_bytes(data[:2], "big")
        return None

    def key(self) -> str:
        return f"{self.mode:02X}:{self.pid:02X}"


# ── Standard decode helpers (SAE J1979 formulas) ────────────────────────────

def _pct(data: bytes) -> float:
    return round(data[0] * 100.0 / 255.0, 2)

def _rpm(data: bytes) -> float:
    return round(((data[0] << 8) | data[1]) / 4.0, 1)

def _temp_c(data: bytes) -> int:
    return data[0] - 40

def _kpa(data: bytes) -> int:
    return data[0]

def _speed_kph(data: bytes) -> int:
    return data[0]

def _volts(data: bytes) -> float:
    return round(((data[0] << 8) | data[1]) / 1000.0, 3)

def _timing_advance(data: bytes) -> float:
    return round(data[0] / 2.0 - 64.0, 1)

def _maf_gs(data: bytes) -> float:
    return round(((data[0] << 8) | data[1]) / 100.0, 2)

def _fuel_trim_pct(data: bytes) -> float:
    return round((data[0] - 128) * 100.0 / 128.0, 1)


# ── Registry ──────────────────────────────────────────────────────────────

class PIDRegistry:
    """
    Central PID registry. Standard PIDs are pre-loaded; OEM plugins can
    register extended PIDs via register().
    """

    def __init__(self) -> None:
        self._defs: Dict[str, PIDDefinition] = {}
        self._load_standard()

    def register(self, definition: PIDDefinition) -> None:
        self._defs[definition.key()] = definition

    def get(self, mode: int, pid: int) -> Optional[PIDDefinition]:
        return self._defs.get(f"{mode:02X}:{pid:02X}")

    def all(self, mode: Optional[int] = None) -> List[PIDDefinition]:
        vals = list(self._defs.values())
        if mode is not None:
            vals = [d for d in vals if d.mode == mode]
        return sorted(vals, key=lambda d: (d.mode, d.pid))

    def decode(self, mode: int, pid: int, data: bytes):
        d = self.get(mode, pid)
        if not d:
            return None
        return d.decode_value(data)

    def to_json(self) -> str:
        return json.dumps(
            [
                {
                    "mode": f"{d.mode:02X}", "pid": f"{d.pid:02X}", "name": d.name,
                    "description": d.description, "unit": d.unit,
                    "bytes": d.bytes_expected, "oem": d.oem,
                }
                for d in self.all()
            ],
            indent=2,
        )

    # ── Standard PID table (subset of SAE J1979, Mode 01 + 09 highlighted;
    #    Modes 02/03/04 reuse Mode 01 PID definitions for freeze frame / are
    #    fixed-format per the spec) ────────────────────────────────────────

    def _load_standard(self) -> None:
        std: List[PIDDefinition] = [
            PIDDefinition(Mode.CURRENT_DATA, 0x00, "PIDS_SUPPORTED_01_20", "PIDs supported [01-20]", 4),
            PIDDefinition(Mode.CURRENT_DATA, 0x04, "ENGINE_LOAD", "Calculated engine load", 1, "%", _pct),
            PIDDefinition(Mode.CURRENT_DATA, 0x05, "COOLANT_TEMP", "Engine coolant temperature", 1, "°C", _temp_c),
            PIDDefinition(Mode.CURRENT_DATA, 0x06, "FUEL_TRIM_SHORT_1", "Short term fuel trim — Bank 1", 1, "%", _fuel_trim_pct),
            PIDDefinition(Mode.CURRENT_DATA, 0x07, "FUEL_TRIM_LONG_1", "Long term fuel trim — Bank 1", 1, "%", _fuel_trim_pct),
            PIDDefinition(Mode.CURRENT_DATA, 0x0A, "FUEL_PRESSURE", "Fuel pressure (gauge)", 1, "kPa", lambda d: d[0] * 3),
            PIDDefinition(Mode.CURRENT_DATA, 0x0B, "INTAKE_MAP", "Intake manifold absolute pressure", 1, "kPa", _kpa),
            PIDDefinition(Mode.CURRENT_DATA, 0x0C, "RPM", "Engine RPM", 2, "rpm", _rpm),
            PIDDefinition(Mode.CURRENT_DATA, 0x0D, "VEHICLE_SPEED", "Vehicle speed", 1, "km/h", _speed_kph),
            PIDDefinition(Mode.CURRENT_DATA, 0x0E, "TIMING_ADVANCE", "Timing advance", 1, "° before TDC", _timing_advance),
            PIDDefinition(Mode.CURRENT_DATA, 0x0F, "INTAKE_TEMP", "Intake air temperature", 1, "°C", _temp_c),
            PIDDefinition(Mode.CURRENT_DATA, 0x10, "MAF", "Mass air flow rate", 2, "g/s", _maf_gs),
            PIDDefinition(Mode.CURRENT_DATA, 0x11, "THROTTLE_POS", "Throttle position", 1, "%", _pct),
            PIDDefinition(Mode.CURRENT_DATA, 0x1F, "RUNTIME", "Run time since engine start", 2, "s",
                          lambda d: (d[0] << 8) | d[1]),
            PIDDefinition(Mode.CURRENT_DATA, 0x21, "MIL_DISTANCE", "Distance traveled with MIL on", 2, "km",
                          lambda d: (d[0] << 8) | d[1]),
            PIDDefinition(Mode.CURRENT_DATA, 0x2F, "FUEL_LEVEL", "Fuel tank level input", 1, "%", _pct),
            PIDDefinition(Mode.CURRENT_DATA, 0x33, "BAROMETRIC", "Absolute barometric pressure", 1, "kPa", _kpa),
            PIDDefinition(Mode.CURRENT_DATA, 0x42, "CONTROL_MODULE_V", "Control module voltage", 2, "V", _volts),
            PIDDefinition(Mode.CURRENT_DATA, 0x43, "ABSOLUTE_LOAD", "Absolute load value", 2, "%",
                          lambda d: round(((d[0] << 8) | d[1]) * 100.0 / 255.0, 1)),
            PIDDefinition(Mode.CURRENT_DATA, 0x46, "AMBIENT_TEMP", "Ambient air temperature", 1, "°C", _temp_c),
            PIDDefinition(Mode.CURRENT_DATA, 0x5C, "OIL_TEMP", "Engine oil temperature", 1, "°C", _temp_c),
            PIDDefinition(Mode.CURRENT_DATA, 0x5E, "FUEL_RATE", "Engine fuel rate", 2, "L/h",
                          lambda d: round(((d[0] << 8) | d[1]) / 20.0, 2)),

            # Mode 09 — vehicle information
            PIDDefinition(Mode.VEHICLE_INFO, 0x00, "INFO_SUPPORTED", "Mode 09 PIDs supported", 4),
            PIDDefinition(Mode.VEHICLE_INFO, 0x02, "VIN", "Vehicle identification number", 17,
                          decode=lambda d: d.decode("ascii", errors="replace").strip()),
            PIDDefinition(Mode.VEHICLE_INFO, 0x04, "CALIBRATION_ID", "Calibration ID", 16,
                          decode=lambda d: d.decode("ascii", errors="replace").strip("\x00 ")),
            PIDDefinition(Mode.VEHICLE_INFO, 0x06, "CVN", "Calibration verification number", 4,
                          decode=lambda d: d.hex().upper()),
            PIDDefinition(Mode.VEHICLE_INFO, 0x0A, "ECU_NAME", "ECU name", 20,
                          decode=lambda d: d.decode("ascii", errors="replace").strip("\x00 ")),
        ]
        for d in std:
            self.register(d)
        # Mode 03/07/0A (stored/pending/permanent DTCs) share a fixed 2-byte
        # DTC-per-entry format handled by src.uds/src.sniffer decoders, not
        # single-PID lookups, so they are intentionally not enumerated here.


REGISTRY = PIDRegistry()


def run(args: argparse.Namespace) -> None:
    mode = int(args.mode, 16) if args.mode else None
    if args.list:
        for d in REGISTRY.all(mode):
            print(f"  {d.mode:02X} {d.pid:02X}  {d.name:22s} {d.description:40s} [{d.unit}]")
    if args.json:
        print(REGISTRY.to_json())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PID registry inspector")
    parser.add_argument("--list", action="store_true", help="List registered PIDs")
    parser.add_argument("--json", action="store_true", help="Dump registry as JSON")
    parser.add_argument("--mode", default=None, help="Filter by mode, e.g. 01")
    run(parser.parse_args())
