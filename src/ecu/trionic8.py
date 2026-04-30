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
                # Decode ASCII, strip null bytes and whitespace padding
                decoded = raw.decode("ascii", errors="replace")
                info[key] = decoded.strip("\x00 \ufffd").strip()
                if not info[key]:
                    info[key] = "[no data]"
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
