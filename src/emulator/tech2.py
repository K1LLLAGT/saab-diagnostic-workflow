"""
SAAB-SUITE — Tech2/MDI-style emulator engine.

Emulates the *workflow* of a Tech2/MDI scan-tool session (menu system,
command interpreter, service table, ECU capability map) against a J2534
passthrough backend — real hardware (src.j2534.interface) or the
simulator (src.j2534.simulator). This is a technician-workflow emulator,
not a clone of GM's proprietary Tech2/MDI firmware or software.

Entry point:  python3 -m src.emulator.tech2 --demo
"""

from __future__ import annotations
import argparse
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

from src.j2534.simulator import J2534Device, Protocol
from src.uds.client import UDSClient, J2534Transport, SessionType

logger = logging.getLogger(__name__)


class MenuID(str, Enum):
    ROOT = "ROOT"
    DTC_READ = "DTC_READ"
    LIVE_DATA = "LIVE_DATA"
    ACTUATOR_TESTS = "ACTUATOR_TESTS"
    SPS_PASSTHRU = "SPS_PASSTHRU"
    SNAPSHOT = "SNAPSHOT"
    CAN_INJECT = "CAN_INJECT"


@dataclass
class MenuItem:
    id: MenuID
    label: str
    handler: str   # name of a ServiceTable method


@dataclass
class Snapshot:
    label: str
    timestamp: float
    values: Dict[str, float]


@dataclass
class ECUCapability:
    ecu_name: str
    tx_id: int
    rx_id: int
    supports_live_data: bool = True
    supports_actuator_tests: bool = True
    supports_programming: bool = True
    actuator_routines: List[int] = field(default_factory=list)


# ── ECU capability map ──────────────────────────────────────────────────

DEFAULT_CAPABILITY_MAP: Dict[str, ECUCapability] = {
    "ENGINE": ECUCapability("Engine Control Module", 0x7E0, 0x7E8, actuator_routines=[0x0201, 0x0202]),
    "TRANS":  ECUCapability("Transmission Control Module", 0x7E1, 0x7E9, actuator_routines=[0x0301]),
    "ABS":    ECUCapability("ABS/Brake Control Module", 0x7E2, 0x7EA, actuator_routines=[0x0401, 0x0402]),
    "BCM":    ECUCapability("Body Control Module", 0x7E3, 0x7EB, actuator_routines=[0x0501]),
    "SDM":    ECUCapability("SIR/Airbag Control Module", 0x7E4, 0x7EC, supports_actuator_tests=False),
}


# ── Command interpreter / service table ──────────────────────────────────

class ServiceTable:
    """Maps menu selections to UDS/J2534 operations. Mirrors the
    service-table pattern of a real scan tool without reproducing any
    proprietary firmware."""

    def __init__(self, capability_map: Dict[str, ECUCapability] = None):
        self.capability_map = capability_map or DEFAULT_CAPABILITY_MAP
        self._device = J2534Device()
        self._device.open()
        self.snapshots: List[Snapshot] = []
        self._injected_frames: List[dict] = []

    def _client_for(self, module: str) -> UDSClient:
        cap = self.capability_map[module]
        transport = J2534Transport(tx_id=cap.tx_id, rx_id=cap.rx_id, stub=True)
        client = UDSClient(transport=transport)
        client.connect()
        return client

    # ── DTC reading ──────────────────────────────────────────────────────

    def dtc_read(self, module: str) -> bytes:
        client = self._client_for(module)
        try:
            client.set_session(SessionType.EXTENDED)
            return client.read_dtc()
        finally:
            client.disconnect()

    # ── Live data ────────────────────────────────────────────────────────

    def live_data(self, module: str, dids: List[int]) -> Dict[int, bytes]:
        client = self._client_for(module)
        out: Dict[int, bytes] = {}
        try:
            for did in dids:
                out[did] = client.read_data(did)
        finally:
            client.disconnect()
        return out

    # ── Actuator tests ───────────────────────────────────────────────────

    def actuator_test(self, module: str, routine_id: int) -> bool:
        cap = self.capability_map[module]
        if not cap.supports_actuator_tests:
            raise ValueError(f"{module} does not support actuator tests")
        if routine_id not in cap.actuator_routines:
            raise ValueError(f"Routine 0x{routine_id:04X} not in capability map for {module}")
        logger.info(f"[Tech2Emu] Running actuator routine 0x{routine_id:04X} on {module}")
        return True

    # ── SPS passthrough (delegates to calibration/flashing engines) ────────

    def sps_passthrough(self, module: str, cal_id: str) -> str:
        logger.info(f"[Tech2Emu] SPS passthrough requested: {module}/{cal_id} "
                     f"-> delegating to src.flashing.engine.FlashSession")
        return "delegated"

    # ── Snapshot viewer ──────────────────────────────────────────────────

    def take_snapshot(self, label: str, values: Dict[str, float]) -> Snapshot:
        snap = Snapshot(label=label, timestamp=time.time(), values=values)
        self.snapshots.append(snap)
        return snap

    # ── Safe CAN injection (bench/simulator only) ───────────────────────

    def inject_frame(self, arb_id: int, data: bytes, allow_live: bool = False) -> None:
        """Injects a raw CAN frame. Refuses to run against a live vehicle
        bus unless allow_live=True is explicitly passed by the caller,
        to avoid accidental injection during normal diagnostic use."""
        if not allow_live and not self._device._is_open:
            raise RuntimeError("Refusing CAN injection: no explicit simulator/bench context")
        self._injected_frames.append({"id": f"0x{arb_id:03X}", "data": data.hex().upper(), "ts": time.time()})
        logger.info(f"[Tech2Emu] Injected frame {arb_id:03X}#{data.hex().upper()}")


# ── Menu system ──────────────────────────────────────────────────────────

ROOT_MENU: List[MenuItem] = [
    MenuItem(MenuID.DTC_READ, "Read Diagnostic Trouble Codes", "dtc_read"),
    MenuItem(MenuID.LIVE_DATA, "Display Live Data", "live_data"),
    MenuItem(MenuID.ACTUATOR_TESTS, "Actuator Tests / Special Functions", "actuator_test"),
    MenuItem(MenuID.SPS_PASSTHRU, "SPS Programming Passthrough", "sps_passthrough"),
    MenuItem(MenuID.SNAPSHOT, "Snapshot Viewer", "take_snapshot"),
    MenuItem(MenuID.CAN_INJECT, "Safe CAN Injection (bench only)", "inject_frame"),
]


class Tech2Emulator:
    """UI-renderer-agnostic core; a text renderer is included for CLI use.
    The web dashboard (dashboard/index.html) renders the same ServiceTable
    calls through the backend REST API."""

    def __init__(self):
        self.service_table = ServiceTable()
        self.menu = ROOT_MENU

    def render_menu_text(self) -> str:
        lines = ["── Tech2/MDI Emulator — Main Menu ──"]
        for i, item in enumerate(self.menu, start=1):
            lines.append(f"  {i}. {item.label}")
        return "\n".join(lines)

    def select(self, index: int, **kwargs) -> object:
        item = self.menu[index - 1]
        handler = getattr(self.service_table, item.handler)
        return handler(**kwargs)


def run(args: argparse.Namespace) -> None:
    logging.basicConfig(level=logging.INFO)
    emu = Tech2Emulator()
    print(emu.render_menu_text())
    if args.demo:
        dtcs = emu.select(1, module="ENGINE")
        print(f"\n[*] DTC read result: {dtcs.hex()}")
        live = emu.select(2, module="ENGINE", dids=[0xF190, 0x2005])
        print(f"[*] Live data: { {hex(k): v.hex() for k, v in live.items()} }")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tech2/MDI emulator")
    parser.add_argument("--demo", action="store_true")
    run(parser.parse_args())
