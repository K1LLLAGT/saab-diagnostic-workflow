"""
SAAB-SUITE — J2534 multi-protocol simulator.

A deterministic, in-process stand-in for a real J2534 pass-thru device
(Mongoose Pro GM II or equivalent), used for development and CI when no
hardware is attached. Implements the same open/connect/read/write/
disconnect/close lifecycle a real PassThru DLL exposes, across the
protocol set required by this suite.

Real hardware backing (Windows PassThru DLL via ctypes) is intentionally
NOT implemented here — see docs/build-instructions.md for wiring a real
`op20pt32.dll`-style vendor driver behind the same Transport interface.

Entry point:  python3 -m src.j2534.simulator --protocol ISO15765 --probe
"""

from __future__ import annotations
import argparse
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class Protocol(str, Enum):
    CAN        = "CAN"
    ISO15765   = "ISO15765"     # ISO-TP over CAN (UDS transport)
    J1850VPW   = "VPW"
    J1850PWM   = "PWM"
    ISO9141    = "ISO9141"
    KWP2000    = "KWP2000"      # ISO14230


@dataclass
class Frame:
    protocol: Protocol
    arb_id: int
    data: bytes
    timestamp: float = field(default_factory=time.time)
    extended: bool = False


class J2534Error(Exception):
    pass


class J2534Device:
    """
    Lifecycle: open() -> connect(protocol) -> read_msg()/write_msg() ->
    disconnect() -> close()

    Mirrors the real PassThruOpen / PassThruConnect / PassThruReadMsgs /
    PassThruWriteMsgs / PassThruDisconnect / PassThruClose call sequence.
    """

    SUPPORTED = {Protocol.CAN, Protocol.ISO15765, Protocol.J1850VPW,
                 Protocol.J1850PWM, Protocol.ISO9141, Protocol.KWP2000}

    def __init__(self, device_name: str = "Mongoose Pro GM II (simulated)"):
        self.device_name = device_name
        self._is_open = False
        self._channel_open = False
        self.protocol: Optional[Protocol] = None
        self.baud: int = 500_000
        self._rx_queue: List[Frame] = []
        self._ecu_sim: Optional[SimulatedECU] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def open(self) -> None:
        logger.info(f"[J2534:open] {self.device_name}")
        self._is_open = True

    def connect(self, protocol: Protocol, baud: int = 500_000) -> None:
        if not self._is_open:
            raise J2534Error("Device not open — call open() first")
        if protocol not in self.SUPPORTED:
            raise J2534Error(f"Protocol {protocol} not supported")
        self.protocol = protocol
        self.baud = baud
        self._channel_open = True
        self._ecu_sim = SimulatedECU(protocol)
        logger.info(f"[J2534:connect] protocol={protocol.value} baud={baud}")

    def write_msg(self, arb_id: int, data: bytes, extended: bool = False) -> None:
        self._require_channel()
        frame = Frame(self.protocol, arb_id, data, extended=extended)
        logger.debug(f"[J2534:tx] {arb_id:03X} {data.hex()}")
        if self._ecu_sim:
            resp = self._ecu_sim.handle(frame)
            if resp:
                self._rx_queue.append(resp)

    def read_msg(self, timeout_ms: int = 1000) -> Optional[Frame]:
        self._require_channel()
        if self._rx_queue:
            return self._rx_queue.pop(0)
        return None

    def disconnect(self) -> None:
        self._channel_open = False
        self.protocol = None
        self._ecu_sim = None
        logger.info("[J2534:disconnect]")

    def close(self) -> None:
        self.disconnect()
        self._is_open = False
        logger.info("[J2534:close]")

    def _require_channel(self) -> None:
        if not self._channel_open:
            raise J2534Error("No open channel — call connect() first")

    # ── Bus probing (used by vehicle auto-detection pipeline) ──────────────

    def probe_all_protocols(self) -> List[Protocol]:
        """Try each supported protocol; return those that yield a bus response."""
        active: List[Protocol] = []
        for proto in self.SUPPORTED:
            try:
                self.connect(proto)
                self.write_msg(0x7DF, bytes([0x02, 0x01, 0x00]))  # OBD-II PID 00 request
                resp = self.read_msg()
                if resp is not None:
                    active.append(proto)
            finally:
                self.disconnect()
        return active


class SimulatedECU:
    """A minimal in-process ECU responder used by the simulator + emulator
    engine so higher layers (UDS client, sniffer, flashing engine) can be
    exercised end-to-end without hardware."""

    RX_ID = 0x7E8
    TX_ID = 0x7E0

    def __init__(self, protocol: Protocol):
        self.protocol = protocol
        self.battery_v = 12.8
        self.ignition_on = True
        self.dtc_count = 0

    def handle(self, frame: Frame) -> Optional[Frame]:
        if frame.arb_id not in (self.TX_ID, 0x7DF):
            return None
        if not frame.data:
            return None
        # OBD-II mode 01 PID 00 -> canned "supported PIDs" bitmap response
        if len(frame.data) >= 3 and frame.data[1] == 0x01:
            payload = bytes([0x06, 0x41, frame.data[2], 0xBE, 0x1F, 0xB8, 0x10])
            return Frame(self.protocol, self.RX_ID, payload)
        return Frame(self.protocol, self.RX_ID, bytes([0x02, 0x7F, frame.data[0]]))


def run(args: argparse.Namespace) -> None:
    logging.basicConfig(level=logging.INFO)
    dev = J2534Device()
    dev.open()
    if args.probe:
        active = dev.probe_all_protocols()
        print(f"[*] Active protocols: {[p.value for p in active]}")
    else:
        dev.connect(Protocol(args.protocol))
        dev.write_msg(0x7DF, bytes([0x02, 0x01, 0x00]))
        resp = dev.read_msg()
        print(f"[*] Response: {resp}")
        dev.disconnect()
    dev.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="J2534 simulator")
    parser.add_argument("--protocol", default="ISO15765", choices=[p.value for p in Protocol])
    parser.add_argument("--probe", action="store_true", help="Probe all protocols")
    run(parser.parse_args())
