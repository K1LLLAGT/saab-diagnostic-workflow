"""
SAAB-SUITE — SPS-style calibration catalog engine.

Directory layout:
    calibrations/<ECU>/index.json          — list of calibration IDs + metadata summary
    calibrations/<ECU>/<cal_id>.json        — full calibration record

Provides VIN lookup (via applicability rules in each record), dependency
resolution, update history, and flash-compatibility checks. This module
manages *metadata* only — it does not embed or generate real ECU binary
images.

Entry point:  python3 -m src.calibration.catalog --ecu T8 --list
"""

from __future__ import annotations
import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class CalibrationRecord:
    cal_id: str
    os_id: str
    calibration_id: str
    cvn: str
    segment_type: str          # e.g. "OS", "CAL", "BOOT", "STRATEGY"
    ecu: str
    applicability: List[str] = field(default_factory=list)   # WMI/VDS patterns or explicit VINs
    depends_on: List[str] = field(default_factory=list)      # other cal_ids required first
    supersedes: Optional[str] = None
    release_date: str = ""
    notes: str = ""

    @classmethod
    def from_json(cls, data: dict) -> "CalibrationRecord":
        return cls(**data)

    def to_json(self) -> dict:
        return self.__dict__


class CalibrationCatalog:
    def __init__(self, root: str = "calibrations"):
        self.root = Path(root)

    def list_ecus(self) -> List[str]:
        if not self.root.exists():
            return []
        return sorted(p.name for p in self.root.iterdir() if p.is_dir())

    def index(self, ecu: str) -> List[dict]:
        index_path = self.root / ecu / "index.json"
        if not index_path.exists():
            return []
        return json.loads(index_path.read_text())

    def get(self, ecu: str, cal_id: str) -> Optional[CalibrationRecord]:
        record_path = self.root / ecu / f"{cal_id}.json"
        if not record_path.exists():
            return None
        return CalibrationRecord.from_json(json.loads(record_path.read_text()))

    def lookup_by_vin(self, vin: str) -> List[CalibrationRecord]:
        """Match VIN against each ECU's calibrations' `applicability`
        patterns. A pattern may be an exact VIN or a WMI/VDS prefix."""
        matches: List[CalibrationRecord] = []
        for ecu in self.list_ecus():
            for entry in self.index(ecu):
                cal_id = entry.get("cal_id") or entry.get("calibration_id")
                record = self.get(ecu, cal_id) if cal_id else None
                if record and self._vin_matches(vin, record.applicability):
                    matches.append(record)
        return matches

    @staticmethod
    def _vin_matches(vin: str, patterns: List[str]) -> bool:
        vin = vin.upper()
        return any(vin == p.upper() or vin.startswith(p.upper()) for p in patterns)

    def resolve_dependencies(self, ecu: str, cal_id: str) -> List[str]:
        """Topologically order a calibration's `depends_on` chain so
        prerequisite segments are flashed before the requested one."""
        order: List[str] = []
        visiting: set = set()

        def visit(current: str) -> None:
            if current in order:
                return
            if current in visiting:
                raise ValueError(f"Circular calibration dependency detected at {current}")
            visiting.add(current)
            record = self.get(ecu, current)
            if record:
                for dep in record.depends_on:
                    visit(dep)
            visiting.discard(current)
            order.append(current)

        visit(cal_id)
        return order

    def check_flash_compatibility(self, ecu: str, cal_id: str, current_os_id: str) -> dict:
        """Compare a target calibration's OS-ID requirement against the
        ECU's currently-installed OS-ID (as read via UDS DID 0xF1A2 / T8
        equivalent)."""
        record = self.get(ecu, cal_id)
        if not record:
            return {"compatible": False, "reason": f"No such calibration {ecu}/{cal_id}"}
        if record.os_id and record.os_id != current_os_id:
            return {
                "compatible": False,
                "reason": f"OS mismatch: catalog expects {record.os_id}, ECU reports {current_os_id}",
            }
        return {"compatible": True, "reason": "OS-ID matches"}

    def update_history(self, ecu: str, cal_id: str) -> List[dict]:
        """Walk the `supersedes` chain backward from cal_id to build a
        chronological update history."""
        history = []
        current = self.get(ecu, cal_id)
        while current:
            history.append({
                "cal_id": current.cal_id,
                "calibration_id": current.calibration_id,
                "release_date": current.release_date,
                "notes": current.notes,
            })
            current = self.get(ecu, current.supersedes) if current.supersedes else None
        return history


def run(args: argparse.Namespace) -> None:
    cat = CalibrationCatalog(args.root)
    if args.list:
        for entry in cat.index(args.ecu):
            print(f"  {entry}")
    if args.vin:
        for rec in cat.lookup_by_vin(args.vin):
            print(f"  {rec.ecu}/{rec.cal_id}  os={rec.os_id} cvn={rec.cvn}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SPS-style calibration catalog")
    parser.add_argument("--root", default="calibrations")
    parser.add_argument("--ecu", default="T8")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--vin", default=None)
    run(parser.parse_args())
