"""
SAAB-SUITE — UDS client (ISO 14229).

Implements the UDS service layer over J2534 CAN (Mongoose Pro GM II).
Used by Trionic T8 and other module communication.

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
import time
import logging
from dataclasses import dataclass, field
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
    """Negative Response Codes."""
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


# ── Transport stub (J2534 / CAN) ─────────────────────────────────────────────

class J2534Transport:
    """
    Thin wrapper around J2534 pass-thru for UDS frame exchange.
    Real implementation connects to the Mongoose Pro GM II DLL.
    Stub mode used when hardware is not connected.
    """

    NEGATIVE_RESPONSE_SID = 0x7F

    def __init__(self, tx_id: int = 0x7E0, rx_id: int = 0x7E8,
                 timeout_ms: int = 1000, stub: bool = True):
        self.tx_id     = tx_id
        self.rx_id     = rx_id
        self.timeout   = timeout_ms / 1000.0
        self.stub      = stub
        self._connected = False

    def connect(self) -> bool:
        if self.stub:
            logger.info("[J2534] Stub mode — no hardware required")
            self._connected = True
            return True
        # TODO: load J2534 DLL, open device, open CAN channel
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
        """Return plausible positive responses for common services."""
        if not payload:
            raise TransportError("Empty payload")
        sid = payload[0]
        pos = sid + 0x40          # positive response SID

        stubs = {
            SID.DIAGNOSTIC_SESSION_CONTROL: bytes([pos, payload[1] if len(payload) > 1 else 0x01]),
            SID.ECU_RESET:                  bytes([pos, 0x01]),
            SID.TESTER_PRESENT:             bytes([pos, 0x00]),
            SID.READ_DATA_BY_ID:            bytes([pos]) + payload[1:3] + b'\xDE\xAD\xBE\xEF',
            SID.SECURITY_ACCESS:            bytes([pos, 0x02, 0x12, 0x34]),
            SID.READ_DTC:                   bytes([pos, 0xFF, 0x00]),
            SID.CLEAR_DTC:                  bytes([pos]),
        }
        return stubs.get(sid, bytes([pos]))


# ── UDS Client ───────────────────────────────────────────────────────────────

class UDSClient:
    """
    High-level UDS client.  Uses J2534Transport for frame exchange.

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

    # ── Session control ──────────────────────────────────────────────────────

    def set_session(self, session: SessionType = SessionType.DEFAULT) -> None:
        payload = bytes([SID.DIAGNOSTIC_SESSION_CONTROL, int(session)])
        resp = self._request(payload)
        self._session = session
        logger.info(f"[UDS] Session: {session.name}")

    # ── Tester present (keep-alive) ──────────────────────────────────────────

    def tester_present(self, suppress_response: bool = True) -> None:
        sub = 0x80 if suppress_response else 0x00
        self._request(bytes([SID.TESTER_PRESENT, sub]))

    # ── Read data by identifier ──────────────────────────────────────────────

    def read_data(self, did: int) -> bytes:
        payload = bytes([SID.READ_DATA_BY_ID, (did >> 8) & 0xFF, did & 0xFF])
        resp = self._request(payload)
        return resp[3:]   # strip positive SID + DID echo

    # ── Security access ──────────────────────────────────────────────────────

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

    # ── DTC handling ─────────────────────────────────────────────────────────

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

    # ── ECU reset ────────────────────────────────────────────────────────────

    def ecu_reset(self, reset_type: ResetType = ResetType.HARD) -> None:
        payload = bytes([SID.ECU_RESET, int(reset_type)])
        self._request(payload)
        logger.info(f"[UDS] ECU reset: {reset_type.name}")

    # ── Internal ─────────────────────────────────────────────────────────────

    def _request(self, payload: bytes) -> bytes:
        logger.debug(f"[UDS] TX: {payload.hex()}")
        resp = self.transport.send_recv(payload)
        logger.debug(f"[UDS] RX: {resp.hex()}")
        if len(resp) >= 3 and resp[0] == J2534Transport.NEGATIVE_RESPONSE_SID:
            raise NegativeResponse(resp[1], resp[2])
        return resp
