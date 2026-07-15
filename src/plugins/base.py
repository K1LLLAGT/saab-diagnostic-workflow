"""
SAAB-SUITE — OEM plugin API contract.

Every OEM plugin (plugins/<oem>/plugin.py) implements OEMPlugin and ships
a manifest.json describing its capabilities. See docs/plugin-api.md for
the full contract and plugins/gm, plugins/ford for reference
implementations.

Security note: `get_security_seed` / `send_security_key` define the
INTERFACE a real seed/key exchange uses. This suite does not ship real
OEM security algorithms — plugins must supply their own, licensed from
the OEM, via SeedKeyProvider. See docs/security-access-disclaimer.md.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class VehicleInfo:
    vin: str
    make: str
    model: str
    year: int
    ecu_targets: List[str] = field(default_factory=list)


@dataclass
class RoutineResult:
    routine_id: int
    success: bool
    detail: str = ""


@dataclass
class FlashBlock:
    address: int
    data: bytes
    block_index: int
    total_blocks: int


class SeedKeyProvider(ABC):
    """Pluggable security-access algorithm. This suite ships no real OEM
    algorithms — see docs/security-access-disclaimer.md. A plugin must
    supply one licensed from (or reverse-engineered with authorization
    from) the OEM before live security access will function outside of
    the simulator."""

    @abstractmethod
    def compute_key(self, seed: bytes, level: int) -> bytes:
        raise NotImplementedError


class NullSeedKeyProvider(SeedKeyProvider):
    """Refuses to compute a real key — used as the default so unlicensed
    deployments fail closed instead of silently sending a wrong key."""

    def compute_key(self, seed: bytes, level: int) -> bytes:
        raise NotImplementedError(
            "No licensed security-access algorithm configured for this ECU. "
            "Supply a SeedKeyProvider via the OEM plugin before requesting "
            "programming-level security access."
        )


class OEMPlugin(ABC):
    """Base class every plugins/<oem>/plugin.py must implement."""

    oem: str = "generic"
    protocols: List[str] = []
    min_year: int = 1996
    max_year: int = 2100

    def __init__(self) -> None:
        self.vehicle: Optional[VehicleInfo] = None
        self.seed_key_provider: SeedKeyProvider = NullSeedKeyProvider()

    @abstractmethod
    def initialize(self, vehicle_info: VehicleInfo) -> None:
        """Bind the plugin to a specific vehicle/ECU set."""

    @abstractmethod
    def get_extended_pids(self) -> List[dict]:
        """Return OEM-extended PID definitions (see src.pid.registry.PIDDefinition)."""

    @abstractmethod
    def decode_response(self, pid: int, data: bytes) -> Any:
        """Decode a raw response for an OEM-extended PID/DID."""

    def get_security_seed(self, level: int = 0x01) -> bytes:
        """Request a security-access seed. Wired to the live UDS client by
        the flashing engine; plugin only needs to override compute rules
        via seed_key_provider."""
        raise NotImplementedError("Wire get_security_seed to a live UDS/KWP transport")

    def send_security_key(self, key: bytes, level: int = 0x01) -> bool:
        raise NotImplementedError("Wire send_security_key to a live UDS/KWP transport")

    @abstractmethod
    def run_routine(self, routine_id: int, params: Optional[bytes] = None) -> RoutineResult:
        """Execute an OEM routine (actuator test, self-test, relearn, etc.)."""

    def prepare_flash(self, cal_file: str) -> Dict[str, Any]:
        """Validate a calibration file against this OEM's expectations
        (checksum/CVN, ECU applicability) prior to flashing. See
        src.calibration.catalog for the SPS-style catalog this reads from."""
        raise NotImplementedError

    def execute_flash(self, blocks: List[FlashBlock]) -> bool:
        """Stream validated blocks to the flashing engine. See
        src.flashing.engine.FlashSession for the block-transfer/flow-control
        implementation this should delegate to."""
        raise NotImplementedError

    def recover_flash(self) -> bool:
        """Attempt ECU recovery-mode reflash after an interrupted session."""
        raise NotImplementedError

    def lookup_calibrations(self, vin: str) -> List[dict]:
        """VIN -> list of applicable calibrations from this OEM's catalog."""
        raise NotImplementedError

    def blocking_dtc_codes(self) -> List[str]:
        """Extra DTC prefixes that should block flashing for this OEM,
        beyond src.flashsafe.checklist.DEFAULT_BLOCKING_DTC_PREFIXES."""
        return []
