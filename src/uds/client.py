"""
SAAB-SUITE — UDS client (ISO 14229).

Implements the UDS service layer over J2534 CAN (Mongoose Pro GM II).

Services implemented:
  0x10  DiagnosticSessionControl
  0x11  ECUReset
  0x14  ClearDiagnosticInformation
  0x19  ReadDTCInformation
  0x22  ReadDataByIdentifier
  0x27  SecurityAccess
  0x2E  WriteDataByIdentifier
  0x31  RoutineControl
  0x34  RequestDownload
  0x36  TransferData
  0x37  RequestTransferExit
  0x3E  TesterPresent
"""

from __future__ import annotations
import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

logger = logging.getLogger(__name__)


# ── UDS Service IDs ──────────────────────────────────────────────────────────

class SID(IntEnum):
    DIAGNOSTIC_SESSION_CONTROL  = 0x10
    ECU_RESET                   = 0x11
    CLEAR_DTC                   = 0x14
    READ_DTC                    = 0x19
    READ_DATA_BY_ID             = 0x22
    SECURITY_ACCESS             = 0x27
    WRITE_DATA_BY_ID            = 0x2E
    ROUTINE_CONTROL             = 0x31
    REQUEST_DOWNLOAD            = 0x34
    TRANSFER_DATA               = 0x36
    REQUEST_TRANSFER_EXIT       = 0x37
    TESTER_PRESENT              = 0x3E


class SessionType(IntEnum):
    DEFAULT     = 0x01
    PROGRAMMING = 0x02
    EXTENDED    = 0x03


class ResetType(IntEnum):
    HARD = 0x01
    SOFT = 0x03


class NRC(IntEnum):
    GENERAL_REJECT                  = 0x10
    SERVICE_NOT_SUPPORTED           = 0x11
    SUB_FUNCTION_NOT_SUPPORTED      = 0x12
    INCORRECT_MESSAGE_LENGTH        = 0x13
    RESPONSE_TOO_LONG               = 0x14
    BUSY_REPEAT_REQUEST             = 0x21
    CONDITIONS_NOT_CORRECT          = 0x22
    REQUEST_SEQUENCE_ERROR          = 0x24
    REQUEST_OUT_OF_RANGE            = 0x31
    SECURITY_ACCESS_DENIED          = 0x33
    INVALID_KEY                     = 0x35
    EXCEEDED_NUMBER_OF_ATTEMPTS     = 0x36
    REQUIRED_TIME_DELAY_NOT_EXPIRED = 0x37
    UPLOAD_DOWNLOAD_NOT_ACCEPTED    = 0x70
    TRANSFER_DATA_SUSPENDED         = 0x71
    GENERAL_PROGRAMMING_FAILURE     = 0x72
    WRONG_BLOCK_SEQUENCE_COUNTER    = 0x73
    RESPONSE_PENDING                = 0x78
    SUB_FUNCTION_NOT_SUPPORTED_ACTIVE_SESSION = 0x7E
    SERVICE_NOT_SUPPORTED_ACTIVE_SESSION      = 0x7F


# ── Exceptions ───────────────────────────────────────────────────────────────

class UDSException(Exception):
    pass

class NegativeResponse(UDSException):
    def __init__(self, sid: int, nrc: int):
        self.sid = sid
        self.nrc = nrc
        nrc_name = NRC(nrc).name if nrc in NRC._value2member_map_ else f"0x{nrc:02X}"
        super().__init__(f"NRC for SID 0x{sid:02X}: {nrc_name}")

class TimeoutError(UDSException):
    pass

class TransportError(UDSException):
    pass


# ── Stub DID response table ───────────────────────────────────────────────────
# Keyed by (DID_HIGH, DID_LOW).
# Values are raw data bytes that follow the positive SID + DID echo.
# Numeric params: big-endian uint16, pre-scaled (scale applied in trionic8.py).
# String params:  ASCII bytes.

_STUB_DID_DATA: dict[tuple[int,int], bytes] = {
    # ── Identification strings ────────────────────────────────────────────
    (0xF1, 0x90): b"YS3FD45Y381234567",   # VIN  (17 chars)
    (0xF1, 0x87): b"55564890        ",     # Part number
    (0xF1, 0x8C): b"T8-2008-B284R   ",    # ECU serial
    (0xF1, 0x97): b"E87 v1.14       ",    # SW version
    (0xF1, 0xA2): b"Trionic8-StageOEM",   # Cal fingerprint

    # ── Live engine data (uint16 big-endian, scaled in trionic8.py) ───────
    # RPM:  850 rpm          → raw 850  (scale ×1)
    (0x20, 0x05): (850  ).to_bytes(2, "big"),
    # Boost: 95 kPa          → raw 950  (scale ×0.1)
    (0x20, 0x01): (950  ).to_bytes(2, "big"),
    # IAT:  22.5 °C          → raw 625  (scale ×0.1, offset -40)  625×0.1-40=22.5
    (0x20, 0x02): (625  ).to_bytes(2, "big"),
    # Coolant: 91 °C         → raw 1310 (scale ×0.1, offset -40)  1310×0.1-40=91
    (0x20, 0x03): (1310 ).to_bytes(2, "big"),
    # Throttle: 3.2%         → raw 32   (scale ×0.1)
    (0x20, 0x04): (32   ).to_bytes(2, "big"),
    # Ign timing: 12.5 °BTDC → raw 125  (scale ×0.1)
    (0x20, 0x06): (125  ).to_bytes(2, "big"),
    # Inj PW: 2.14 ms        → raw 214  (scale ×0.01)
    (0x20, 0x07): (214  ).to_bytes(2, "big"),
    # Lambda: 1.00           → raw 100  (scale ×0.01)
    (0x20, 0x08): (100  ).to_bytes(2, "big"),
    # Knock retard: 0.0°     → raw 0
    (0x20, 0x09): (0    ).to_bytes(2, "big"),
    # Wastegate duty: 12%    → raw 120  (scale ×0.1)
    (0x20, 0x0A): (120  ).to_bytes(2, "big"),
    # Haldex: 0%             → raw 0
    (0x20, 0x0B): (0    ).to_bytes(2, "big"),
    # Battery: 14.1 V        → raw 141  (scale ×0.1)
    (0x20, 0x0C): (141  ).to_bytes(2, "big"),
    # Speed: 0 km/h          → raw 0
    (0x20, 0x0D): (0    ).to_bytes(2, "big"),
    # MAF: 2.8 g/s           → raw 28   (scale ×0.1)
    (0x20, 0x0E): (28   ).to_bytes(2, "big"),
    # Fuel trim ST: +1.2%    → raw 1012 (scale ×0.1, offset -100)
    (0x20, 0x0F): (1012 ).to_bytes(2, "big"),
    # Fuel trim LT: -0.4%    → raw 996  (scale ×0.1, offset -100)
    (0x20, 0x10): (996  ).to_bytes(2, "big"),
}


# ── Transport stub (J2534 / CAN) ─────────────────────────────────────────────

class J2534Transport:
    """
    Thin wrapper around J2534 pass-thru for UDS frame exchange.
    Stub mode used when hardware is not connected.
    """

    NEGATIVE_RESPONSE_SID = 0x7F

    def __init__(self, tx_id: int = 0x7E0, rx_id: int = 0x7E8,
                 timeout_ms: int = 1000, stub: bool = True):
        self.tx_id      = tx_id
        self.rx_id      = rx_id
        self.timeout    = timeout_ms / 1000.0
        self.stub       = stub
        self._connected = False

    def connect(self) -> bool:
        if self.stub:
            logger.info("[J2534] Stub mode — no hardware required")
            self._connected = True
            return True
        raise NotImplementedError("Live J2534 connection not yet wired")

    def disconnect(self) -> None:
        self._connected = False
        logger.info("[J2534] Disconnected")

    def send_recv(self, payload: bytes) -> bytes:
        if not self._connected:
            raise TransportError("Not connected — call connect() first")
        if self.stub:
            return self._stub_response(payload)
        raise NotImplementedError("Live send/recv not yet wired")

    def _stub_response(self, payload: bytes) -> bytes:
        """Return realistic positive responses per service / DID."""
        if not payload:
            raise TransportError("Empty payload")

        sid = payload[0]
        pos = sid + 0x40   # positive response SID

        # ReadDataByIdentifier — look up per-DID stub data
        if sid == SID.READ_DATA_BY_ID and len(payload) >= 3:
            dh, dl = payload[1], payload[2]
            data = _STUB_DID_DATA.get((dh, dl), b"\x00\x00")
            return bytes([pos, dh, dl]) + data

        # Generic stubs for other services
        generic = {
            SID.DIAGNOSTIC_SESSION_CONTROL: bytes([pos, payload[1] if len(payload) > 1 else 0x01]),
            SID.ECU_RESET:                  bytes([pos, 0x01]),
            SID.TESTER_PRESENT:             bytes([pos, 0x00]),
            SID.SECURITY_ACCESS:            bytes([pos, 0x02, 0x12, 0x34]),
            SID.READ_DTC:                   bytes([pos, 0xFF, 0x00]),
            SID.CLEAR_DTC:                  bytes([pos]),
        }
        return generic.get(sid, bytes([pos]))


# ── UDS Client ───────────────────────────────────────────────────────────────

class UDSClient:
    """
    High-level UDS client.

    Example:
        client = UDSClient()
        client.connect()
        client.set_session(SessionType.EXTENDED)
        vin = client.read_data(0xF190)
        client.disconnect()
    """

    def __init__(self, transport: Optional[J2534Transport] = None):
        self.transport = transport or J2534Transport(stub=True)
        self._session  = SessionType.DEFAULT

    def connect(self) -> None:
        ok = self.transport.connect()
        if ok:
            logger.info("[UDS] Transport connected")

    def disconnect(self) -> None:
        self.transport.disconnect()

    def set_session(self, session: SessionType = SessionType.DEFAULT) -> None:
        payload = bytes([SID.DIAGNOSTIC_SESSION_CONTROL, int(session)])
        self._request(payload)
        self._session = session
        logger.info(f"[UDS] Session: {session.name}")

    def tester_present(self, suppress_response: bool = True) -> None:
        sub = 0x80 if suppress_response else 0x00
        self._request(bytes([SID.TESTER_PRESENT, sub]))

    def read_data(self, did: int) -> bytes:
        payload = bytes([SID.READ_DATA_BY_ID, (did >> 8) & 0xFF, did & 0xFF])
        resp = self._request(payload)
        return resp[3:]   # strip positive SID + DID echo (3 bytes)

    def security_access(self, level: int = 0x01) -> bytes:
        payload = bytes([SID.SECURITY_ACCESS, level])
        resp = self._request(payload)
        seed = resp[2:]
        logger.info(f"[UDS] Security seed: {seed.hex()}")
        return seed

    def send_security_key(self, level: int, key: bytes) -> None:
        payload = bytes([SID.SECURITY_ACCESS, level + 1]) + key
        self._request(payload)
        logger.info("[UDS] Security access granted")

    def read_dtc(self, sub: int = 0xFF, mask: int = 0x00) -> bytes:
        payload = bytes([SID.READ_DTC, sub, mask])
        resp = self._request(payload)
        return resp[1:]

    def clear_dtc(self, group: int = 0xFFFFFF) -> None:
        payload = bytes([SID.CLEAR_DTC,
                         (group >> 16) & 0xFF,
                         (group >>  8) & 0xFF,
                          group        & 0xFF])
        self._request(payload)
        logger.info("[UDS] DTCs cleared")

    def ecu_reset(self, reset_type: ResetType = ResetType.HARD) -> None:
        payload = bytes([SID.ECU_RESET, int(reset_type)])
        self._request(payload)
        logger.info(f"[UDS] ECU reset: {reset_type.name}")

    def _request(self, payload: bytes) -> bytes:
        logger.debug(f"[UDS] TX: {payload.hex()}")
        resp = self.transport.send_recv(payload)
        logger.debug(f"[UDS] RX: {resp.hex()}")
        if len(resp) >= 3 and resp[0] == J2534Transport.NEGATIVE_RESPONSE_SID:
            raise NegativeResponse(resp[1], resp[2])
        return resp
