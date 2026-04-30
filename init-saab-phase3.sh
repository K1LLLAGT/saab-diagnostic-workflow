#!/usr/bin/env bash
set -euo pipefail

ROOTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[*] SAAB-SUITE Phase 3 — UDS / T8 / VIN logging / dashboard..."

mkdir -p \
  src/uds \
  src/ecu \
  src/logging \
  dashboard \
  data/sessions

##################################
# 1) src/uds/client.py
#    ISO 14229 UDS over J2534/CAN
##################################
cat > src/uds/client.py << 'EOF'
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
EOF

##################################
# 2) src/ecu/trionic8.py
#    B284R / Trionic T8 ECU module
##################################
cat > src/ecu/trionic8.py << 'EOF'
"""
SAAB-SUITE — Trionic T8 ECU module.

Target:   2008 SAAB 9-3 XWD Aero
Engine:   B284R  (GM corporate code: A28NER)
ECU:      Trionic T8 (Bosch ME9.6 derivative)
Trans:    AF40-6
AWD:      Haldex Gen4

CAN IDs (HS-CAN, 500 kbps):
  ECU TX  0x7E0
  ECU RX  0x7E8

Trionic T8 DIDs (ReadDataByIdentifier 0x22):
  0xF190  VIN
  0xF187  Part number
  0xF18C  ECU serial number
  0xF197  System supplier ECU software version
  0xF1A2  Calibration software fingerprint
  0x2001  Boost pressure (kPa)
  0x2002  Intake air temp (°C)
  0x2003  Coolant temp (°C)
  0x2004  Throttle position (%)
  0x2005  Engine RPM
  0x2006  Ignition timing (°BTDC)
  0x2007  Injector pulse width (ms)
  0x2008  Lambda (×100)
  0x2009  Knock retard (°)
  0x200A  Turbo wastegate duty (%)
  0x200B  Haldex clutch engagement (%)
  0x200C  Battery voltage (×10 V)
  0x200D  Vehicle speed (km/h)
  0x200E  Mass air flow (g/s ×10)
  0x200F  Fuel trim short-term (%)
  0x2010  Fuel trim long-term (%)

Security:  Trionic T8 uses a 16-bit seed/key algorithm.
           Seed is returned on SecurityAccess(0x01).
           Key = ~seed XOR 0x4A4D  (simplified; full algo in t8_keygen).
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict

from src.uds.client import UDSClient, J2534Transport, SessionType, ResetType

logger = logging.getLogger(__name__)


# ── B284R-specific Data IDs ───────────────────────────────────────────────────

DID = {
    "VIN":                  0xF190,
    "PART_NUMBER":          0xF187,
    "ECU_SERIAL":           0xF18C,
    "SW_VERSION":           0xF197,
    "CAL_FINGERPRINT":      0xF1A2,
    "BOOST_KPA":            0x2001,
    "IAT_C":                0x2002,
    "COOLANT_C":            0x2003,
    "THROTTLE_PCT":         0x2004,
    "RPM":                  0x2005,
    "IGN_TIMING":           0x2006,
    "INJ_PW_MS":            0x2007,
    "LAMBDA":               0x2008,
    "KNOCK_RETARD":         0x2009,
    "WASTEGATE_DUTY":       0x200A,
    "HALDEX_ENGAGEMENT":    0x200B,
    "BATTERY_V":            0x200C,
    "VEHICLE_SPEED":        0x200D,
    "MAF_GS":               0x200E,
    "FUEL_TRIM_ST":         0x200F,
    "FUEL_TRIM_LT":         0x2010,
}

# Reverse map: DID int → name
DID_NAME: Dict[int, str] = {v: k for k, v in DID.items()}


# ── Parsed live data ──────────────────────────────────────────────────────────

@dataclass
class T8LiveData:
    vin:                str   = ""
    rpm:                int   = 0
    boost_kpa:          float = 0.0
    iat_c:              float = 0.0
    coolant_c:          float = 0.0
    throttle_pct:       float = 0.0
    ign_timing:         float = 0.0
    inj_pw_ms:          float = 0.0
    lambda_:            float = 0.0
    knock_retard:       float = 0.0
    wastegate_duty:     float = 0.0
    haldex_engagement:  float = 0.0
    battery_v:          float = 0.0
    vehicle_speed:      int   = 0
    maf_gs:             float = 0.0
    fuel_trim_st:       float = 0.0
    fuel_trim_lt:       float = 0.0


# ── T8 security key generator ─────────────────────────────────────────────────

def t8_keygen(seed: bytes) -> bytes:
    """
    Trionic T8 security key derivation.
    Simplified public algorithm — sufficient for extended diagnostic session.
    Full BSL/programming unlock requires OEM algorithm.
    seed: 2-byte seed from SecurityAccess(0x01) response
    """
    if len(seed) < 2:
        raise ValueError("Seed must be 2 bytes")
    s = (seed[0] << 8) | seed[1]
    key = (~s ^ 0x4A4D) & 0xFFFF
    return bytes([(key >> 8) & 0xFF, key & 0xFF])


# ── Trionic8 high-level interface ─────────────────────────────────────────────

class Trionic8:
    """
    High-level interface to the Trionic T8 ECU on the B284R.

    Usage:
        t8 = Trionic8()
        t8.connect()
        info = t8.read_ecu_info()
        live = t8.read_live_data()
        dtcs = t8.read_dtcs()
        t8.disconnect()
    """

    ECU_TX_ID = 0x7E0
    ECU_RX_ID = 0x7E8

    def __init__(self, stub: bool = True):
        transport = J2534Transport(
            tx_id=self.ECU_TX_ID,
            rx_id=self.ECU_RX_ID,
            stub=stub
        )
        self.uds   = UDSClient(transport=transport)
        self._stub = stub

    def connect(self) -> None:
        self.uds.connect()
        self.uds.set_session(SessionType.EXTENDED)
        logger.info("[T8] Connected — extended session active")

    def disconnect(self) -> None:
        self.uds.set_session(SessionType.DEFAULT)
        self.uds.disconnect()
        logger.info("[T8] Disconnected")

    # ── ECU identification ────────────────────────────────────────────────────

    def read_ecu_info(self) -> Dict[str, str]:
        info = {}
        id_keys = ["VIN", "PART_NUMBER", "ECU_SERIAL", "SW_VERSION", "CAL_FINGERPRINT"]
        for key in id_keys:
            try:
                raw = self.uds.read_data(DID[key])
                info[key] = raw.decode("ascii", errors="replace").strip("\x00 ")
            except Exception as e:
                info[key] = f"[error: {e}]"
        return info

    # ── Live data ─────────────────────────────────────────────────────────────

    def read_live_data(self) -> T8LiveData:
        d = T8LiveData()

        def _read_int(name: str) -> int:
            try:
                raw = self.uds.read_data(DID[name])
                return int.from_bytes(raw[:2], "big") if len(raw) >= 2 else 0
            except Exception:
                return 0

        def _read_float(name: str, scale: float = 1.0) -> float:
            return _read_int(name) * scale

        d.rpm              = _read_int("RPM")
        d.boost_kpa        = _read_float("BOOST_KPA", 0.1)
        d.iat_c            = _read_float("IAT_C", 0.1) - 40.0
        d.coolant_c        = _read_float("COOLANT_C", 0.1) - 40.0
        d.throttle_pct     = _read_float("THROTTLE_PCT", 0.1)
        d.ign_timing       = _read_float("IGN_TIMING", 0.1)
        d.inj_pw_ms        = _read_float("INJ_PW_MS", 0.01)
        d.lambda_          = _read_float("LAMBDA", 0.01)
        d.knock_retard     = _read_float("KNOCK_RETARD", 0.1)
        d.wastegate_duty   = _read_float("WASTEGATE_DUTY", 0.1)
        d.haldex_engagement= _read_float("HALDEX_ENGAGEMENT", 0.1)
        d.battery_v        = _read_float("BATTERY_V", 0.1)
        d.vehicle_speed    = _read_int("VEHICLE_SPEED")
        d.maf_gs           = _read_float("MAF_GS", 0.1)
        d.fuel_trim_st     = _read_float("FUEL_TRIM_ST", 0.1) - 100.0
        d.fuel_trim_lt     = _read_float("FUEL_TRIM_LT", 0.1) - 100.0

        try:
            vin_raw = self.uds.read_data(DID["VIN"])
            d.vin = vin_raw.decode("ascii", errors="replace").strip("\x00 ")
        except Exception:
            d.vin = "UNKNOWN"

        return d

    # ── DTCs ──────────────────────────────────────────────────────────────────

    def read_dtcs(self) -> bytes:
        return self.uds.read_dtc()

    def clear_dtcs(self) -> None:
        self.uds.clear_dtc()
        logger.info("[T8] DTCs cleared")

    # ── Security unlock (extended diag) ──────────────────────────────────────

    def unlock_extended(self) -> None:
        seed = self.uds.security_access(level=0x01)
        key  = t8_keygen(seed)
        self.uds.send_security_key(level=0x01, key=key)
        logger.info("[T8] Extended security unlocked")

    # ── ECU reset ─────────────────────────────────────────────────────────────

    def reset(self, hard: bool = True) -> None:
        self.uds.ecu_reset(ResetType.HARD if hard else ResetType.SOFT)


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)

    t8 = Trionic8(stub=True)
    t8.connect()

    print("\n── ECU Info ──")
    info = t8.read_ecu_info()
    for k, v in info.items():
        print(f"  {k:25s} {v}")

    print("\n── Live Data (stub) ──")
    live = t8.read_live_data()
    print(f"  RPM:              {live.rpm}")
    print(f"  Boost:            {live.boost_kpa:.1f} kPa")
    print(f"  Coolant:          {live.coolant_c:.1f} °C")
    print(f"  IAT:              {live.iat_c:.1f} °C")
    print(f"  Throttle:         {live.throttle_pct:.1f} %")
    print(f"  Ignition timing:  {live.ign_timing:.1f} °BTDC")
    print(f"  Lambda:           {live.lambda_:.2f}")
    print(f"  Knock retard:     {live.knock_retard:.1f} °")
    print(f"  Wastegate duty:   {live.wastegate_duty:.1f} %")
    print(f"  Haldex:           {live.haldex_engagement:.1f} %")
    print(f"  Battery:          {live.battery_v:.1f} V")
    print(f"  Speed:            {live.vehicle_speed} km/h")
    print(f"  MAF:              {live.maf_gs:.1f} g/s")
    print(f"  Fuel trim ST:     {live.fuel_trim_st:+.1f} %")
    print(f"  Fuel trim LT:     {live.fuel_trim_lt:+.1f} %")

    t8.disconnect()
EOF

##################################
# 3) src/logging/session.py  (VIN-tagged, JSON)
##################################
cat > src/logging/session.py << 'EOF'
"""
SAAB-SUITE — VIN-tagged session logger.

Each diagnostic run creates a structured directory:

  logs/
    <VIN>/
      <YYYYMMDD-HHMM>-<prefix>/
        session.json   ← machine-readable structured log
        session.log    ← human-readable plaintext log

session.json schema:
  {
    "vin":       "YS3FD45Y381234567",
    "prefix":    "diag",
    "started":   "2024-01-15T14:32:00",
    "ended":     null,
    "host":      "kali-rog",
    "entries":   [
      {"ts": "14:32:00.123", "level": "INFO", "msg": "..."},
      ...
    ],
    "summary":   { "errors": 0, "warnings": 0, "dtc_count": 0 }
  }
"""

from __future__ import annotations
import json
import os
import platform
import datetime
import pathlib
import logging
from typing import List, Dict, Any, Optional


class SessionLogger:
    """
    VIN-tagged, JSON + plaintext session logger.

    Usage:
        log = SessionLogger(vin="YS3FD45Y381234567", prefix="diag")
        log.info("Connected to T8")
        log.warning("J2534 probe failed")
        log.finalize(dtc_count=3)
    """

    DEFAULT_VIN = "UNKNOWN_VIN"

    def __init__(self, vin: str = DEFAULT_VIN,
                 prefix: str = "diag",
                 root: str = "logs"):
        self.vin    = vin.strip().upper() or self.DEFAULT_VIN
        self.prefix = prefix
        ts          = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        self.run_dir = pathlib.Path(root) / self.vin / f"{ts}-{prefix}"
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self._log_path  = self.run_dir / "session.log"
        self._json_path = self.run_dir / "session.json"

        self._entries: List[Dict[str, Any]] = []
        self._errors   = 0
        self._warnings = 0

        self._session: Dict[str, Any] = {
            "vin":     self.vin,
            "prefix":  self.prefix,
            "started": datetime.datetime.now().isoformat(timespec="seconds"),
            "ended":   None,
            "host":    platform.node(),
            "entries": self._entries,
            "summary": {},
        }

        self._write_json()
        self.info(f"Session started — VIN: {self.vin}  host: {platform.node()}")

    # ── Public logging API ────────────────────────────────────────────────────

    def info(self, msg: str) -> None:
        self._append("INFO", msg)

    def warning(self, msg: str) -> None:
        self._warnings += 1
        self._append("WARN", msg)

    def error(self, msg: str) -> None:
        self._errors += 1
        self._append("ERROR", msg)

    def data(self, label: str, value: Any) -> None:
        self._append("DATA", f"{label} = {value}")

    # ── Finalise ──────────────────────────────────────────────────────────────

    def finalize(self, dtc_count: int = 0) -> None:
        self._session["ended"] = datetime.datetime.now().isoformat(timespec="seconds")
        self._session["summary"] = {
            "errors":    self._errors,
            "warnings":  self._warnings,
            "dtc_count": dtc_count,
        }
        self._write_json()
        self.info(
            f"Session ended — errors={self._errors} "
            f"warnings={self._warnings} dtcs={dtc_count}"
        )

    # ── Path helpers ──────────────────────────────────────────────────────────

    @property
    def path(self) -> pathlib.Path:
        return self.run_dir

    @property
    def json_path(self) -> pathlib.Path:
        return self._json_path

    # ── Internal ──────────────────────────────────────────────────────────────

    def _append(self, level: str, msg: str) -> None:
        ts   = datetime.datetime.now().strftime("%H:%M:%S.%f")[:12]
        line = f"[{ts}] [{level:5s}] {msg}"
        print(line)
        with open(self._log_path, "a") as f:
            f.write(line + "\n")
        self._entries.append({"ts": ts, "level": level, "msg": msg})
        self._write_json()

    def _write_json(self) -> None:
        with open(self._json_path, "w") as f:
            json.dump(self._session, f, indent=2)
EOF

##################################
# 4) dashboard/index.html
#    HTML diagnostic dashboard
##################################
cat > dashboard/index.html << 'HTMLEOF'
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SAAB-SUITE Diagnostic Dashboard</title>
  <style>
    :root {
      --bg:       #0d0f14;
      --surface:  #161a22;
      --border:   #2a2f3d;
      --accent:   #e8a020;
      --accent2:  #4a9eff;
      --text:     #d0d4dc;
      --muted:    #6b7280;
      --error:    #ef4444;
      --warn:     #f59e0b;
      --ok:       #22c55e;
      --font-mono: "JetBrains Mono", "Fira Code", "Courier New", monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg); color: var(--text);
      font-family: var(--font-mono); font-size: 13px;
      min-height: 100vh;
    }

    /* ── Header ── */
    header {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 14px 24px;
      display: flex; align-items: center; justify-content: space-between;
    }
    .logo { color: var(--accent); font-size: 18px; font-weight: 700; letter-spacing: 2px; }
    .logo span { color: var(--text); font-weight: 400; }
    .vin-badge {
      background: #1e2230; border: 1px solid var(--border);
      padding: 4px 12px; border-radius: 4px;
      color: var(--accent2); font-size: 12px;
    }

    /* ── Layout ── */
    .layout { display: grid; grid-template-columns: 220px 1fr; min-height: calc(100vh - 53px); }
    nav {
      background: var(--surface); border-right: 1px solid var(--border);
      padding: 16px 0;
    }
    nav a {
      display: block; padding: 9px 20px;
      color: var(--muted); text-decoration: none; font-size: 12px;
      border-left: 3px solid transparent; transition: all 0.15s;
    }
    nav a:hover, nav a.active {
      color: var(--text); border-left-color: var(--accent);
      background: rgba(232,160,32,0.07);
    }
    nav .section-label {
      padding: 14px 20px 6px; color: var(--muted);
      font-size: 10px; letter-spacing: 1.5px; text-transform: uppercase;
    }
    main { padding: 24px; overflow-y: auto; }

    /* ── Panels ── */
    .panel { display: none; }
    .panel.active { display: block; }
    .panel-title {
      font-size: 15px; color: var(--accent); margin-bottom: 18px;
      border-bottom: 1px solid var(--border); padding-bottom: 10px;
    }

    /* ── Cards ── */
    .card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; margin-bottom: 20px; }
    .card {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 6px; padding: 14px;
    }
    .card-label { color: var(--muted); font-size: 11px; margin-bottom: 6px; }
    .card-value { font-size: 22px; font-weight: 700; color: var(--text); }
    .card-unit  { font-size: 11px; color: var(--muted); margin-left: 4px; }
    .card.ok    { border-left: 3px solid var(--ok); }
    .card.warn  { border-left: 3px solid var(--warn); }
    .card.error { border-left: 3px solid var(--error); }

    /* ── Live data grid ── */
    .live-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
      gap: 10px;
    }
    .live-cell {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 5px; padding: 12px;
    }
    .live-cell .lc-name  { color: var(--muted); font-size: 10px; margin-bottom: 4px; }
    .live-cell .lc-value { font-size: 18px; font-weight: 700; }
    .live-cell .lc-unit  { font-size: 10px; color: var(--muted); margin-left: 3px; }

    /* ── DTC table ── */
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 9px 12px; text-align: left; border-bottom: 1px solid var(--border); }
    th { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }
    td { font-size: 12px; }
    .badge {
      display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 10px; font-weight: 700;
    }
    .badge-error  { background: rgba(239,68,68,0.15);  color: var(--error); }
    .badge-warn   { background: rgba(245,158,11,0.15); color: var(--warn); }
    .badge-ok     { background: rgba(34,197,94,0.15);  color: var(--ok); }
    .badge-info   { background: rgba(74,158,255,0.15); color: var(--accent2); }

    /* ── Log viewer ── */
    .log-viewer {
      background: #0a0c10; border: 1px solid var(--border); border-radius: 5px;
      padding: 14px; height: 420px; overflow-y: auto; font-size: 11px; line-height: 1.7;
    }
    .log-INFO  { color: #9ca3af; }
    .log-DATA  { color: var(--accent2); }
    .log-WARN  { color: var(--warn); }
    .log-ERROR { color: var(--error); }

    /* ── Session list ── */
    .session-list { display: flex; flex-direction: column; gap: 8px; }
    .session-item {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 5px; padding: 12px 16px;
      display: flex; justify-content: space-between; align-items: center;
      cursor: pointer; transition: border-color 0.15s;
    }
    .session-item:hover { border-color: var(--accent); }
    .session-item .si-vin { color: var(--accent2); font-size: 12px; }
    .session-item .si-ts  { color: var(--muted); font-size: 11px; }
    .session-item .si-meta { text-align: right; }

    /* ── Toolbar ── */
    .toolbar {
      display: flex; gap: 10px; margin-bottom: 16px;
    }
    .btn {
      background: var(--surface); border: 1px solid var(--border);
      color: var(--text); padding: 7px 14px; border-radius: 4px;
      cursor: pointer; font-family: var(--font-mono); font-size: 12px;
      transition: all 0.15s;
    }
    .btn:hover   { border-color: var(--accent); color: var(--accent); }
    .btn.primary { background: var(--accent); color: #000; border-color: var(--accent); font-weight: 700; }
    .btn.primary:hover { background: #f5b040; }

    /* ── ECU info table ── */
    .info-table { width: 100%; border-collapse: collapse; }
    .info-table tr:nth-child(even) td { background: rgba(255,255,255,0.02); }
    .info-table td { padding: 8px 12px; border-bottom: 1px solid var(--border); font-size: 12px; }
    .info-table td:first-child { color: var(--muted); width: 220px; }

    /* ── Status bar ── */
    .statusbar {
      position: fixed; bottom: 0; left: 0; right: 0;
      background: var(--surface); border-top: 1px solid var(--border);
      padding: 5px 20px; display: flex; gap: 20px; font-size: 11px; color: var(--muted);
    }
    .statusbar .dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 5px; }
    .dot-ok    { background: var(--ok); }
    .dot-error { background: var(--error); }
    .dot-warn  { background: var(--warn); }
  </style>
</head>
<body>

<header>
  <div class="logo">SAAB<span>-SUITE</span> &nbsp;·&nbsp; Diagnostic Dashboard</div>
  <div class="vin-badge" id="header-vin">VIN: —</div>
</header>

<div class="layout">
  <nav>
    <div class="section-label">Overview</div>
    <a href="#" class="active" data-panel="overview">◈ &nbsp;Overview</a>
    <a href="#" data-panel="live">⬡ &nbsp;Live Data</a>

    <div class="section-label">Diagnostics</div>
    <a href="#" data-panel="dtc">⚠ &nbsp;Fault Codes</a>
    <a href="#" data-panel="ecu-info">◻ &nbsp;ECU Info</a>

    <div class="section-label">Sessions</div>
    <a href="#" data-panel="sessions">☰ &nbsp;Session Log</a>
    <a href="#" data-panel="log-viewer">⌨ &nbsp;Raw Log</a>
  </nav>

  <main>
    <!-- Overview -->
    <div class="panel active" id="panel-overview">
      <div class="panel-title">System Overview — 2008 SAAB 9-3 XWD Aero / B284R / T8</div>
      <div class="card-grid">
        <div class="card ok">
          <div class="card-label">ECU STATUS</div>
          <div class="card-value" id="ov-ecu-status">—</div>
        </div>
        <div class="card" id="card-j2534">
          <div class="card-label">J2534 / MONGOOSE</div>
          <div class="card-value" id="ov-j2534">—</div>
        </div>
        <div class="card" id="card-dtc">
          <div class="card-label">ACTIVE DTCs</div>
          <div class="card-value" id="ov-dtc-count">—</div>
        </div>
        <div class="card ok">
          <div class="card-label">SESSION</div>
          <div class="card-value" id="ov-session">—</div>
        </div>
        <div class="card">
          <div class="card-label">LAST RUN</div>
          <div class="card-value" style="font-size:13px" id="ov-last-run">—</div>
        </div>
        <div class="card">
          <div class="card-label">VIN</div>
          <div class="card-value" style="font-size:12px" id="ov-vin">—</div>
        </div>
      </div>
    </div>

    <!-- Live Data -->
    <div class="panel" id="panel-live">
      <div class="panel-title">Live Data — B284R Engine Parameters</div>
      <div class="toolbar">
        <button class="btn primary" onclick="refreshLive()">⟳ &nbsp;Refresh</button>
        <button class="btn" onclick="exportLive()">↓ &nbsp;Export JSON</button>
      </div>
      <div class="live-grid" id="live-grid"></div>
    </div>

    <!-- DTC -->
    <div class="panel" id="panel-dtc">
      <div class="panel-title">Fault Codes (DTCs)</div>
      <div class="toolbar">
        <button class="btn primary" onclick="readDTCs()">⟳ &nbsp;Read DTCs</button>
        <button class="btn" onclick="clearDTCs()">✕ &nbsp;Clear DTCs</button>
      </div>
      <table>
        <thead>
          <tr><th>Code</th><th>Description</th><th>Status</th><th>Module</th></tr>
        </thead>
        <tbody id="dtc-tbody"></tbody>
      </table>
    </div>

    <!-- ECU Info -->
    <div class="panel" id="panel-ecu-info">
      <div class="panel-title">ECU Identification — Trionic T8</div>
      <table class="info-table" id="ecu-info-table"></table>
    </div>

    <!-- Sessions -->
    <div class="panel" id="panel-sessions">
      <div class="panel-title">Session History</div>
      <div class="toolbar">
        <button class="btn" onclick="loadSessions()">⟳ &nbsp;Refresh</button>
      </div>
      <div class="session-list" id="session-list"></div>
    </div>

    <!-- Raw Log -->
    <div class="panel" id="panel-log-viewer">
      <div class="panel-title">Raw Session Log</div>
      <div class="toolbar">
        <button class="btn" onclick="loadLog()">⟳ &nbsp;Reload</button>
        <button class="btn" onclick="clearLogView()">✕ &nbsp;Clear view</button>
      </div>
      <div class="log-viewer" id="log-viewer"></div>
    </div>

  </main>
</div>

<div class="statusbar">
  <span><span class="dot dot-ok"></span>Python OK</span>
  <span id="sb-j2534"><span class="dot dot-warn"></span>J2534: checking...</span>
  <span id="sb-session">No session loaded</span>
  <span id="sb-time"></span>
</div>

<script>
// ── State ──────────────────────────────────────────────────────────────────
const state = {
  vin:     "YS3FD45Y381234567",   // Your 9-3's VIN — update here
  session: null,
  liveData: null,
};

// ── Stub data (replaced by live backend when J2534 connected) ──────────────
const STUB_ECU_INFO = {
  "VIN":             "YS3FD45Y381234567",
  "PART_NUMBER":     "55564890",
  "ECU_SERIAL":      "T8-2008-B284R",
  "SW_VERSION":      "E87 v1.14",
  "CAL_FINGERPRINT": "Trionic8-StageOEM",
};

const STUB_LIVE = [
  { name:"RPM",           value:850,   unit:"rpm",    warn: v=>v>6500 },
  { name:"BOOST",         value:95.0,  unit:"kPa",    warn: v=>v>200 },
  { name:"IAT",           value:22.5,  unit:"°C",     warn: v=>v>55 },
  { name:"COOLANT",       value:91.0,  unit:"°C",     warn: v=>v>105 },
  { name:"THROTTLE",      value:3.2,   unit:"%",      warn: ()=>false },
  { name:"IGN TIMING",    value:12.5,  unit:"°BTDC",  warn: ()=>false },
  { name:"INJ PW",        value:2.14,  unit:"ms",     warn: ()=>false },
  { name:"LAMBDA",        value:1.00,  unit:"λ",      warn: v=>v<0.85||v>1.15 },
  { name:"KNOCK RETARD",  value:0.0,   unit:"°",      warn: v=>v>5 },
  { name:"WASTEGATE",     value:12.0,  unit:"% duty", warn: ()=>false },
  { name:"HALDEX",        value:0.0,   unit:"%",      warn: ()=>false },
  { name:"BATTERY",       value:14.1,  unit:"V",      warn: v=>v<11.5||v>15.5 },
  { name:"SPEED",         value:0,     unit:"km/h",   warn: ()=>false },
  { name:"MAF",           value:2.8,   unit:"g/s",    warn: ()=>false },
  { name:"FUEL TRIM ST",  value:+1.2,  unit:"%",      warn: v=>Math.abs(v)>10 },
  { name:"FUEL TRIM LT",  value:-0.4,  unit:"%",      warn: v=>Math.abs(v)>15 },
];

const STUB_DTCS = [
  // empty by default — populated when DTCs present
];

// ── Nav ────────────────────────────────────────────────────────────────────
document.querySelectorAll("nav a").forEach(a => {
  a.addEventListener("click", e => {
    e.preventDefault();
    const id = a.dataset.panel;
    document.querySelectorAll("nav a").forEach(x => x.classList.remove("active"));
    document.querySelectorAll(".panel").forEach(x => x.classList.remove("active"));
    a.classList.add("active");
    document.getElementById("panel-" + id).classList.add("active");
  });
});

// ── Init ───────────────────────────────────────────────────────────────────
function init() {
  document.getElementById("header-vin").textContent = "VIN: " + state.vin;
  document.getElementById("ov-vin").textContent     = state.vin;
  document.getElementById("ov-ecu-status").textContent = "ONLINE (stub)";
  document.getElementById("ov-j2534").textContent      = "DISCONNECTED";
  document.getElementById("card-j2534").className       = "card warn";
  document.getElementById("ov-dtc-count").textContent   = STUB_DTCS.length;
  document.getElementById("card-dtc").className          = STUB_DTCS.length > 0 ? "card error" : "card ok";
  document.getElementById("ov-session").textContent     = "STUB";
  document.getElementById("ov-last-run").textContent    = new Date().toLocaleString();
  document.getElementById("sb-j2534").innerHTML =
    '<span class="dot dot-warn"></span>J2534: disconnected (stub)';
  document.getElementById("sb-session").textContent = "VIN: " + state.vin;

  renderLive();
  renderECUInfo();
  renderDTCs();
  updateClock();
}

// ── Live data ──────────────────────────────────────────────────────────────
function renderLive() {
  const grid = document.getElementById("live-grid");
  grid.innerHTML = "";
  STUB_LIVE.forEach(item => {
    const isWarn = item.warn(item.value);
    const cell = document.createElement("div");
    cell.className = "live-cell";
    cell.innerHTML = `
      <div class="lc-name">${item.name}</div>
      <div class="lc-value" style="color:${isWarn ? "var(--warn)" : "var(--text)"}">
        ${typeof item.value === "number" && !Number.isInteger(item.value)
          ? item.value.toFixed(1) : item.value}
        <span class="lc-unit">${item.unit}</span>
      </div>`;
    grid.appendChild(cell);
  });
}

function refreshLive() {
  // Jitter stub values slightly to simulate live polling
  STUB_LIVE.forEach(item => {
    if (typeof item.value === "number") {
      item.value = +(item.value * (0.97 + Math.random() * 0.06)).toFixed(
        item.unit === "rpm" || item.unit === "km/h" ? 0 : 1
      );
    }
  });
  renderLive();
}

function exportLive() {
  const data = {};
  STUB_LIVE.forEach(i => { data[i.name] = { value: i.value, unit: i.unit }; });
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `live-data-${state.vin}-${Date.now()}.json`;
  a.click();
}

// ── ECU info ───────────────────────────────────────────────────────────────
function renderECUInfo() {
  const tbl = document.getElementById("ecu-info-table");
  tbl.innerHTML = Object.entries(STUB_ECU_INFO).map(([k, v]) =>
    `<tr><td>${k}</td><td>${v}</td></tr>`
  ).join("");
}

// ── DTCs ───────────────────────────────────────────────────────────────────
function renderDTCs() {
  const tbody = document.getElementById("dtc-tbody");
  if (STUB_DTCS.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" style="color:var(--ok);text-align:center;padding:20px">
      No active fault codes</td></tr>`;
    return;
  }
  tbody.innerHTML = STUB_DTCS.map(d => `
    <tr>
      <td style="color:var(--accent2)">${d.code}</td>
      <td>${d.desc}</td>
      <td><span class="badge badge-${d.severity}">${d.status}</span></td>
      <td>${d.module}</td>
    </tr>`).join("");
}

function readDTCs() {
  // Stub — would call Python backend over local API when connected
  renderDTCs();
  appendLog("INFO", "DTC read requested (stub mode)");
}

function clearDTCs() {
  STUB_DTCS.length = 0;
  renderDTCs();
  document.getElementById("ov-dtc-count").textContent = "0";
  document.getElementById("card-dtc").className = "card ok";
  appendLog("INFO", "DTCs cleared (stub)");
}

// ── Log viewer ─────────────────────────────────────────────────────────────
const _logLines = [];
function appendLog(level, msg) {
  const ts = new Date().toTimeString().slice(0,8);
  _logLines.push({ ts, level, msg });
  renderLog();
}
function renderLog() {
  const viewer = document.getElementById("log-viewer");
  viewer.innerHTML = _logLines.map(e =>
    `<div class="log-${e.level}">[${e.ts}] [${e.level.padEnd(5)}] ${e.msg}</div>`
  ).join("");
  viewer.scrollTop = viewer.scrollHeight;
}
function loadLog() { renderLog(); }
function clearLogView() { _logLines.length = 0; renderLog(); }

// ── Sessions ───────────────────────────────────────────────────────────────
function loadSessions() {
  const list = document.getElementById("session-list");
  const stubs = [
    { vin: state.vin, ts: "2024-01-15 14:32", prefix: "diag",  errors: 0, dtcs: 0 },
    { vin: state.vin, ts: "2024-01-12 09:18", prefix: "scan",  errors: 0, dtcs: 2 },
    { vin: state.vin, ts: "2024-01-10 17:05", prefix: "diag",  errors: 1, dtcs: 1 },
  ];
  list.innerHTML = stubs.map(s => `
    <div class="session-item">
      <div>
        <div class="si-vin">${s.vin}</div>
        <div style="font-size:11px;color:var(--muted);margin-top:3px">${s.prefix.toUpperCase()} run</div>
      </div>
      <div class="si-meta">
        <div class="si-ts">${s.ts}</div>
        <div style="margin-top:4px">
          <span class="badge ${s.errors>0 ? 'badge-error' : 'badge-ok'}">
            ${s.errors} errors
          </span>
          &nbsp;
          <span class="badge ${s.dtcs>0 ? 'badge-warn' : 'badge-ok'}">
            ${s.dtcs} DTCs
          </span>
        </div>
      </div>
    </div>`).join("");
}

// ── Clock ──────────────────────────────────────────────────────────────────
function updateClock() {
  document.getElementById("sb-time").textContent = new Date().toLocaleTimeString();
  setTimeout(updateClock, 1000);
}

// ── Startup log entries ────────────────────────────────────────────────────
appendLog("INFO", "SAAB-SUITE Dashboard initialised");
appendLog("INFO", `VIN: ${state.vin}`);
appendLog("INFO", "ECU: Trionic T8 / B284R");
appendLog("WARN", "J2534 interface not connected — stub mode active");
appendLog("DATA", "Platform: Win7-SAAB VM / Mongoose Pro GM II");

loadSessions();
init();
</script>
</body>
</html>
HTMLEOF

##################################
# 5) Update scripts/diagnostic_scan.py
#    Wire VIN-tagged SessionLogger
##################################
cat > scripts/diagnostic_scan.py << 'EOF'
#!/usr/bin/env python3
"""
SAAB-SUITE — Diagnostic scan script (Phase 3).

Orchestrates: analyzer → J2534 probe → CAN probe → T8 live data
All output tagged to VIN and written to structured JSON session log.
"""

import sys
import argparse
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from src.analysis.analyzer   import check_environment
from src.j2534.interface     import test_interface
from src.can.bus             import probe_can
from src.ecu.trionic8        import Trionic8
from src.logging.session     import SessionLogger

# ── Default VIN: 2008 SAAB 9-3 XWD Aero ──────────────────────────────────
DEFAULT_VIN = "YS3FD45Y381234567"


def main() -> None:
    parser = argparse.ArgumentParser(description="SAAB-SUITE diagnostic scan")
    parser.add_argument("--vin",  default=DEFAULT_VIN, help="Vehicle VIN")
    parser.add_argument("--stub", action="store_true",  default=True,
                        help="Stub mode (no hardware required)")
    args = parser.parse_args()

    log = SessionLogger(vin=args.vin, prefix="scan")
    log.info(f"diagnostic_scan.py started  vin={args.vin}  stub={args.stub}")

    # [1/4] Environment
    log.info("[1/4] Environment check...")
    if not check_environment():
        log.error("Environment check failed")
        sys.exit(1)
    log.info("Environment: OK")

    # [2/4] J2534
    log.info("[2/4] J2534 interface probe...")
    j2534_ok = test_interface()
    if j2534_ok:
        log.info("J2534 / Mongoose: OK")
    else:
        log.warning("J2534 not found — continuing in stub mode")

    # [3/4] CAN
    log.info("[3/4] CAN bus probe...")
    can_ok = probe_can("j2534", "mongoose")
    if can_ok:
        log.info("CAN bus: OK")
    else:
        log.warning("CAN probe failed — stub mode")

    # [4/4] T8 live data
    log.info("[4/4] Trionic T8 ECU read...")
    t8 = Trionic8(stub=args.stub)
    t8.connect()

    info = t8.read_ecu_info()
    for k, v in info.items():
        log.data(k, v)

    live = t8.read_live_data()
    log.data("RPM",           live.rpm)
    log.data("BOOST_KPA",     live.boost_kpa)
    log.data("COOLANT_C",     live.coolant_c)
    log.data("IAT_C",         live.iat_c)
    log.data("THROTTLE_PCT",  live.throttle_pct)
    log.data("IGN_TIMING",    live.ign_timing)
    log.data("LAMBDA",        live.lambda_)
    log.data("KNOCK_RETARD",  live.knock_retard)
    log.data("WASTEGATE",     live.wastegate_duty)
    log.data("HALDEX",        live.haldex_engagement)
    log.data("BATTERY_V",     live.battery_v)
    log.data("SPEED",         live.vehicle_speed)
    log.data("MAF_GS",        live.maf_gs)
    log.data("FUEL_TRIM_ST",  live.fuel_trim_st)
    log.data("FUEL_TRIM_LT",  live.fuel_trim_lt)

    dtc_raw = t8.read_dtcs()
    dtc_count = max(0, (len(dtc_raw) - 1) // 3)
    log.data("DTC_COUNT", dtc_count)

    t8.disconnect()

    log.finalize(dtc_count=dtc_count)
    print(f"\n[*] Session log: {log.json_path}")


if __name__ == "__main__":
    main()
EOF
chmod +x scripts/diagnostic_scan.py

echo ""
echo "[*] Phase 3 complete."
echo ""
echo "Test the stack:"
echo "  python3 -m src.ecu.trionic8"
echo "  python3 scripts/diagnostic_scan.py"
echo "  open dashboard/index.html"
echo ""
echo "Then commit:"
echo "  git add -A && git commit -m 'feat: Phase 3 — UDS/T8/VIN-logging/dashboard' && git push"

