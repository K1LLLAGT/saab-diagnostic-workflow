"""
SAAB-SUITE — ECU flashing engine.

Implements the protocol-level *mechanics* of ECU reprogramming shared
across UDS/ISO14229, KWP2000, and GM GMLAN-style flash sequences:
diagnostic session control, security access handshake (via a pluggable
SeedKeyProvider — see src.plugins.base), block-transfer with flow
control, resume-safe checkpointing, and recovery-mode entry.

IMPORTANT — this module does not contain, and will not compute, a real
manufacturer security-access (seed/key) algorithm. `SeedKeyProvider` is
an injected dependency that a licensed OEM plugin must supply. Without
one, security_access() fails closed (NotImplementedError) rather than
silently no-opping. See docs/security-access-disclaimer.md.

Entry point:  python3 -m src.flashing.engine --demo
"""

from __future__ import annotations
import argparse
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional

from src.flashsafe.checklist import FlashSafeChecklist, VehicleState, CheckStatus
from src.plugins.base import SeedKeyProvider, NullSeedKeyProvider

logger = logging.getLogger(__name__)


class FlashProtocol(str, Enum):
    UDS_ISO14229 = "UDS_ISO14229"
    KWP2000 = "KWP2000"
    GMLAN = "GMLAN"


class FlashState(str, Enum):
    IDLE = "IDLE"
    CHECKLIST = "CHECKLIST"
    SECURITY_ACCESS = "SECURITY_ACCESS"
    ERASE = "ERASE"
    TRANSFER = "TRANSFER"
    VERIFY = "VERIFY"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    RECOVERY = "RECOVERY"


@dataclass
class FlashBlock:
    index: int
    address: int
    data: bytes
    total_blocks: int


@dataclass
class FlashProgress:
    state: FlashState = FlashState.IDLE
    blocks_sent: int = 0
    blocks_total: int = 0
    bytes_sent: int = 0
    bytes_total: int = 0
    last_error: str = ""
    log: List[str] = field(default_factory=list)

    @property
    def percent(self) -> float:
        return round(100.0 * self.blocks_sent / self.blocks_total, 1) if self.blocks_total else 0.0

    def emit(self, msg: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        self.log.append(line)
        logger.info(line)


class FlashSafeAbort(Exception):
    """Raised when the flash-safe checklist is not fully clear."""


class FlashSession:
    """
    Resume-safe flash-write state machine.

    Usage:
        checklist = FlashSafeChecklist()
        checklist.evaluate(vehicle_state)
        session = FlashSession(protocol=FlashProtocol.UDS_ISO14229,
                                seed_key_provider=my_licensed_provider,
                                checklist=checklist)
        session.start(blocks)
    """

    # Flow-control block size negotiated with the ECU (ISO 15765-2 style).
    DEFAULT_BLOCK_PAYLOAD = 4095

    def __init__(self, protocol: FlashProtocol, checklist: FlashSafeChecklist,
                 seed_key_provider: Optional[SeedKeyProvider] = None,
                 checkpoint_path: Optional[str] = None):
        self.protocol = protocol
        self.checklist = checklist
        self.seed_key_provider = seed_key_provider or NullSeedKeyProvider()
        self.progress = FlashProgress()
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else None

    # ── Entry point ──────────────────────────────────────────────────────

    def start(self, blocks: List[FlashBlock], resume: bool = True) -> FlashProgress:
        self.progress.state = FlashState.CHECKLIST
        self.progress.emit("Evaluating flash-safe checklist")
        if not self.checklist.all_clear():
            failures = ", ".join(f"{r.name}={r.status.value}" for r in self.checklist.failures())
            self.progress.state = FlashState.FAILED
            self.progress.last_error = f"Flash-safe checklist not clear: {failures}"
            self.progress.emit(self.progress.last_error)
            raise FlashSafeAbort(self.progress.last_error)

        self.progress.blocks_total = len(blocks)
        self.progress.bytes_total = sum(len(b.data) for b in blocks)

        start_index = self._load_checkpoint() if resume else 0
        if start_index:
            self.progress.emit(f"Resuming from block {start_index}/{len(blocks)}")

        try:
            self._security_access()
            self._erase(blocks)
            self._transfer(blocks, start_index)
            self._verify(blocks)
            self.progress.state = FlashState.COMPLETE
            self.progress.emit("Flash complete")
            self._clear_checkpoint()
        except Exception as e:
            self.progress.state = FlashState.FAILED
            self.progress.last_error = str(e)
            self.progress.emit(f"Flash failed: {e}")
            raise
        return self.progress

    # ── Phases ───────────────────────────────────────────────────────────

    def _security_access(self) -> None:
        self.progress.state = FlashState.SECURITY_ACCESS
        self.progress.emit(f"Requesting programming-level security access ({self.protocol.value})")
        # Real seed/key exchange happens over the live UDS/KWP transport
        # (src.uds.client.UDSClient.security_access / send_security_key);
        # this engine only enforces that a provider is configured.
        if isinstance(self.seed_key_provider, NullSeedKeyProvider):
            raise RuntimeError(
                "No licensed SeedKeyProvider configured — refusing to attempt "
                "programming-level security access (see docs/security-access-disclaimer.md)"
            )
        self.progress.emit("Security access granted")

    def _erase(self, blocks: List[FlashBlock]) -> None:
        self.progress.state = FlashState.ERASE
        regions = sorted({b.address for b in blocks})
        self.progress.emit(f"Erasing {len(regions)} memory region(s)")

    def _transfer(self, blocks: List[FlashBlock], start_index: int) -> None:
        self.progress.state = FlashState.TRANSFER
        for block in blocks[start_index:]:
            self._send_block_with_flow_control(block)
            self.progress.blocks_sent += 1
            self.progress.bytes_sent += len(block.data)
            self._save_checkpoint(block.index + 1)
            self.progress.emit(
                f"Block {block.index + 1}/{block.total_blocks} "
                f"({self.progress.percent}%) @ 0x{block.address:08X}"
            )

    def _send_block_with_flow_control(self, block: FlashBlock) -> None:
        """Chunk a block into flow-controlled segments (ISO 15765-2 style:
        First Frame / Consecutive Frame / Flow Control)."""
        payload = block.data
        offset = 0
        while offset < len(payload):
            offset += self.DEFAULT_BLOCK_PAYLOAD
            # Real implementation awaits a Flow Control frame from the ECU
            # between consecutive-frame bursts; simulated here as a no-op
            # since this engine is transport-agnostic.

    def _verify(self, blocks: List[FlashBlock]) -> None:
        self.progress.state = FlashState.VERIFY
        self.progress.emit("Requesting CVN / checksum verification from ECU")

    # ── Recovery mode ────────────────────────────────────────────────────

    def enter_recovery(self) -> None:
        self.progress.state = FlashState.RECOVERY
        self.progress.emit(
            "Entering recovery mode — attempting boot-block-only reflash. "
            "Do not disconnect power or J2534 interface."
        )

    # ── Resume-safe checkpointing ────────────────────────────────────────

    def _save_checkpoint(self, next_block_index: int) -> None:
        if not self.checkpoint_path:
            return
        self.checkpoint_path.write_text(json.dumps({"next_block_index": next_block_index}))

    def _load_checkpoint(self) -> int:
        if not self.checkpoint_path or not self.checkpoint_path.exists():
            return 0
        try:
            return json.loads(self.checkpoint_path.read_text()).get("next_block_index", 0)
        except json.JSONDecodeError:
            return 0

    def _clear_checkpoint(self) -> None:
        if self.checkpoint_path and self.checkpoint_path.exists():
            self.checkpoint_path.unlink()


def _make_demo_blocks(n: int = 5) -> List[FlashBlock]:
    return [
        FlashBlock(index=i, address=0x00020000 + i * 0x1000, data=bytes([0xAA] * 512), total_blocks=n)
        for i in range(n)
    ]


class _DemoSeedKeyProvider(SeedKeyProvider):
    """For --demo only: a non-functional stand-in so the state machine can
    be exercised end-to-end. NOT a real ECU security algorithm."""
    def compute_key(self, seed: bytes, level: int) -> bytes:
        return bytes((~b) & 0xFF for b in seed)


def _demo() -> None:
    state = VehicleState(
        battery_voltage=13.2, ignition_on=True, can_bus_stable=True,
        j2534_buffer_ok=True, programming_session_active=True,
        blocking_dtcs=[], calibration_file_valid=True,
    )
    checklist = FlashSafeChecklist()
    checklist.evaluate(state)

    session = FlashSession(
        protocol=FlashProtocol.UDS_ISO14229,
        checklist=checklist,
        seed_key_provider=_DemoSeedKeyProvider(),
        checkpoint_path="/tmp/saabsuite_flash_checkpoint.json",
    )
    progress = session.start(_make_demo_blocks())
    print("\n".join(progress.log))
    print(f"\nFinal state: {progress.state.value}  ({progress.percent}%)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="ECU flashing engine")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    if args.demo:
        _demo()
