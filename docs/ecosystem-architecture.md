# SAAB-SUITE ecosystem architecture

This extends `docs/architecture.md` (the original single-vehicle
Trionic T8 workflow) to the broader technician-tooling layer added
alongside it. Read `docs/security-access-disclaimer.md` first if you're
here for the flashing/security-access pieces specifically — real OEM
security algorithms are explicitly out of scope.

## Layers

```
┌─────────────────────────────────────────────────────────────────┐
│  UI layer                                                        │
│   dashboard/index.html (GDS2-style web dashboard, desktop-hostable│
│   via Electron/webview) · android/ (transport reference only)     │
├─────────────────────────────────────────────────────────────────┤
│  Vehicle abstraction layer                                        │
│   src/ecu/trionic8.py · src/uds/client.py                         │
├─────────────────────────────────────────────────────────────────┤
│  J2534 transport layer                                            │
│   src/j2534/interface.py (hardware probe)                         │
│   src/j2534/simulator.py (in-process multi-protocol simulator)    │
│   android/.../UsbOtgTransport.kt · RemoteCanTransport.kt           │
├─────────────────────────────────────────────────────────────────┤
│  PID / service definition layer                                   │
│   src/pid/registry.py (SAE J1979 modes 01/02/03/04/09)             │
│   plugins/<oem>/pids_<oem>_extended.json (OEM extended PIDs)       │
├─────────────────────────────────────────────────────────────────┤
│  Plugin layer                                                     │
│   src/plugins/base.py (OEMPlugin contract)                        │
│   src/plugins/loader.py (manifest discovery + dynamic import)      │
│   plugins/gm/, plugins/ford/ (reference implementations)          │
├─────────────────────────────────────────────────────────────────┤
│  Sniffer engine        src/sniffer/engine.py                      │
│  Flash-safe engine     src/flashsafe/checklist.py                 │
│  Flashing engine       src/flashing/engine.py                     │
│  Emulator engine       src/emulator/tech2.py                      │
│  Calibration catalog   src/calibration/catalog.py + calibrations/ │
├─────────────────────────────────────────────────────────────────┤
│  Cloud sync engine      src/cloud/sync.py  ←→  backend/app/*      │
│  Remote diagnostics     src/remote/client.py ←→ backend/app/       │
│                          websocket_remote.py                       │
└─────────────────────────────────────────────────────────────────┘
```

## Vehicle auto-detection pipeline

`src/j2534/simulator.py::J2534Device.probe_all_protocols()` tries each
supported protocol (CAN, ISO15765, VPW, PWM, ISO9141, KWP2000) and
reports which yield a bus response. A full pipeline chains this with
VIN request/decode and ECU enumeration:

```python
from src.j2534.simulator import J2534Device
from src.vin.decoder import decode as decode_vin
from src.pid.registry import REGISTRY, Mode

dev = J2534Device()
dev.open()
active_protocols = dev.probe_all_protocols()
dev.connect(active_protocols[0])
dev.write_msg(0x7DF, bytes([0x02, 0x09, 0x02]))   # Mode 09 PID 02 = VIN
vin_frame = dev.read_msg()
vin_info = decode_vin(vin_frame.data[2:].decode("ascii", errors="replace"))
```

ECU enumeration and PID-map loading then follow from the decoded VIN via
`src.calibration.catalog.CalibrationCatalog.lookup_by_vin` and the
relevant OEM plugin's `get_extended_pids()`.

## Real-time streaming

`src/pid/registry.py` PID definitions carry `min_hz`/`max_hz` bounds
(10–50 Hz range) for the UI layer to respect when polling. Multi-PID
batching is a transport-layer concern (issue several `read_data(did)`
calls per polling tick and coalesce into one dashboard update) — see
`dashboard/index.html`'s `refreshLive()` for the client-side pattern.

## Logging

`src/logging/session.py` (pre-existing) already implements VIN-tagged,
JSON+plaintext session logging under `logs/<VIN>/<timestamp>-<prefix>/`.
CSV/JSON export with the `YYYYMMDDHHMMSS<VIN>_log.csv` naming convention
layers on top of that session directory — write a small export helper
alongside it when a concrete UI needs it; the schema in
`SessionLogger._session` already has everything required (timestamps,
VIN, structured entries).

## What's a full implementation vs. a scaffold here

Built and tested end-to-end (unit tests in `tests/` and
`backend/tests/`):

- PID registry, VIN decoder, CAN sniffer engine, flash-safe checklist,
  flashing state machine (protocol mechanics only — see security
  disclaimer), Tech2/MDI-style emulator core, OEM plugin loader +
  two reference plugins, SPS-style calibration catalog, cloud sync
  offline cache/queue, FastAPI cloud + remote-diagnostics backend
  (OAuth2, RBAC, WebSocket session hub, encrypted-at-rest notes), and
  the GDS2-style web dashboard (all panels wired to live demo data,
  smoke-tested headlessly).

Architecture + protocol spec, not a full application:

- **Android**: transport-layer reference code (USB-OTG, Remote CAN)
  and protocol docs — not a full Activity/UI/background-service app.
- **Windows desktop packaging**: the dashboard is plain HTML/CSS/JS and
  can be hosted in Electron or any webview shell; no Electron project
  scaffold is included here.
- **Real ECU flashing / security access**: protocol state machine only.
  See `docs/security-access-disclaimer.md`.
- **GlobalTIS/SPS/Techline Connect programming**: this suite's
  `src/calibration/catalog.py` and `src/flashing/engine.py` follow the
  same conceptual shape (VIN lookup → catalog → dependency resolution →
  flash session) but do not interoperate with GM's actual GlobalTIS/SPS
  servers or Techline Connect — those are closed, licensed systems.
