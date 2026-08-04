# Hybrid Hardware Blueprint — Pi 5 + Mini PC + Workstation

This document specifies a three-tier hardware platform that extends
SAAB-SUITE's existing software stack (`src/`, `backend/`, `dashboard/`)
onto dedicated hardware: a Raspberry Pi 5 vehicle-side capture unit, an
Intel N100 mini-PC that hosts licensed OEM Windows diagnostic software
through a custom J2534 bridge, and a ROG Strix workstation for firmware
analysis and calibration-archive management.

**Scope boundary — read this first.** Everything below builds *around*
two hard limits already established in this repo and preserved here
without exception:

1. **No real OEM security-access (seed/key) algorithm is included or
   derived.** See `docs/security-access-disclaimer.md`. The custom
   hardware and safety system in this document gate and log flashing —
   they do not unlock it. Real unlock keys come from your own licensed
   `SeedKeyProvider` (dealer subscription, licensed tool vendor
   agreement), never from reverse-engineering captured traffic.
2. **The custom J2534 hardware targets the open SAE J2534‑1/‑2 API**,
   the same public standard Drew Technologies, OpenPort, Kvaser, and
   every other independent pass-through vendor implement. It does **not**
   clone a specific vendor's USB VID/PID, serial-number format, or
   licensing handshake to impersonate a Mongoose Pro GM II or VCX Nano to
   a specific OEM tool. Doing that is a DMCA anti-circumvention /
   vendor-ToS problem, not a hardware-engineering one, and it's outside
   what this document does. "Behave like a Mongoose/VCX Nano" here means
   *functional parity through the standard API* — any J2534-compliant
   software (Tech2Win, TIS2000, GDS2, GM SPS, Ford FMP, generic J2534
   scan tools) talks to it the same way it talks to any certified
   pass-through device. OEM software licensing (Techstream, ISTA, ODIS,
   ACDelco TDS, HDS) is assumed to be your own legitimate
   dealer/subscription access — this document doesn't address obtaining
   or bypassing those licenses.

Everything else — capture, calibration ID detection, calibration
archive, cloud sync, PCB, enclosure, bootloader — is a straightforward,
legal hardware/software integration project, comparable to what
independent repair shops already build and buy.

## Table of contents

1. [System data flow](#1-system-data-flow)
2. [Hardware build steps](#2-hardware-build-steps)
3. [Software build steps](#3-software-build-steps)
4. [Final assembly](#4-final-assembly)
5. [Additional requirements](#5-additional-requirements)
6. [Optional expansions](#6-optional-expansions)
7. [Wiring diagrams](#7-wiring-diagrams)
8. [J2534 driver emulation](#8-j2534-driver-emulation)
9. [Calibration database system](#9-calibration-database-system)
10. [Firmware flashing safety system](#10-firmware-flashing-safety-system)
11. [Hardware bill of materials](#11-hardware-bill-of-materials)
12. [Enclosure design](#12-enclosure-design)
13. [CAN/LIN protocol decoding](#13-canlin-protocol-decoding)
14. [PCB design](#14-pcb-design)
15. [Bootloader design](#15-bootloader-design)
16. [Cloud architecture](#16-cloud-architecture)
17. [Manufacturing & supply chain](#17-manufacturing--supply-chain)
18. [Full technical architecture diagram](#18-full-technical-architecture-diagram)
19. [Embedded Linux optimization](#19-embedded-linux-optimization)

---

## 1. System data flow

```
┌────────────┐   CAN/LIN (500k HS-CAN)   ┌─────────────────────┐
│  Vehicle   │──────────────────────────▶│  Raspberry Pi 5      │
│ (Saab 9-3  │◀──────────────────────────│  capture unit        │
│  Aero XWD) │      OBD-II request       │  src/can, src/vin,   │
└────────────┘                            │  src/pid, src/uds    │
                                           └──────────┬───────────┘
                                                       │ USB-Ethernet / Wi-Fi
                                                       │ (metadata: VIN, cal ID,
                                                       │  OS-ID, CVN, DTCs)
                                                       ▼
                                           ┌─────────────────────┐
                                           │  Mini PC (N100)      │
                                           │  Windows 11          │
                                           │  J2534 bridge driver │
                                           │  + OEM tool (Tech2Win│
                                           │  / TIS2000 / GDS2 /  │
                                           │  Techstream / ISTA)  │
                                           └──────────┬───────────┘
                                                       │ J2534 pass-through
                                                       │ (flash / live data)
                                                       ▼
                                           ┌────────────┐
                                           │  Vehicle   │
                                           └────────────┘
                                                       │
                                            firmware dump / session log
                                                       │ 2.5GbE / USB3 NVMe
                                                       ▼
                                           ┌─────────────────────┐
                                           │  Full PC workstation │
                                           │  (ROG Strix)          │
                                           │  reverse-engineering, │
                                           │  calibration DB build │
                                           └──────────┬───────────┘
                                                       │ rclone sync
                                                       ▼
                                           ┌─────────────────────┐
                                           │  Google Drive         │
                                           │  calibration archive  │
                                           └─────────────────────┘
```

### 1.1 Vehicle → Raspberry Pi

- Physical link: OBD-II port pins 6 (CAN-H) / 14 (CAN-L), 500 kbps HS-CAN
  for the Trionic T8 (`src/ecu/trionic8.py` documents `0x7E0`/`0x7E8`).
  LIN taps (if used for accessory modules) come off the GPIO header, not
  OBD-II — see [Section 7](#7-wiring-diagrams).
- `src/sniffer/engine.py` performs raw frame capture and timestamping;
  `src/j2534/simulator.py::probe_all_protocols()` performs protocol
  auto-detection (CAN, ISO15765, VPW, PWM, ISO9141, KWP2000) the same
  way a bench tool would when it doesn't yet know what's on the bus.
- Calibration ID detection: after VIN decode (`src/vin/decoder.py`),
  `src/uds/client.py::read_data(0xF1A2)` (T8 calibration fingerprint DID)
  plus `0xF187`/`0xF197` (part number / software version) are read and
  handed to `src/calibration/catalog.py::check_flash_compatibility()`.

### 1.2 Raspberry Pi → Mini PC

- Transport: USB-Ethernet gadget mode (Pi 5 acting as a USB device to
  the mini-PC) or LAN/Wi-Fi, carrying a small JSON metadata message —
  VIN, ECU, current OS-ID/CVN, active DTCs, calibration catalog matches.
  This is the same payload shape `src/remote/client.py` and
  `backend/app/websocket_remote.py` already define for the
  remote-diagnostics WebSocket channel; reuse that schema rather than
  inventing a second one.
- The Mini PC's calibration-selector service (new, [Section 3](#3-software-build-steps))
  receives this metadata, queries the local calibration cache
  (mirrored from `calibrations/` via rclone — [Section 9](#9-calibration-database-system)),
  and resolves the correct flash file + dependency order via
  `CalibrationCatalog.resolve_dependencies()`.

### 1.3 Mini PC → Vehicle

- The Mini PC runs the licensed OEM tool (Tech2Win, TIS2000, GDS2, GM
  SPS/ACDelco TDS, Ford FMP, Honda HDS, Techstream, ISTA, ODIS) against
  the custom J2534 bridge ([Section 8](#8-j2534-driver-emulation)),
  which forwards pass-through calls to the same physical CAN transceiver
  the Pi 5 used for capture (see [Section 4](#4-final-assembly) for how
  the two units share or hand off the physical bus connection).
- All flash operations pass through `src/flashsafe/checklist.py` +
  `src/flashing/engine.py`'s state machine first — see
  [Section 10](#10-firmware-flashing-safety-system).

### 1.4 Mini PC → Full PC

- Firmware dumps, session logs (`logs/<VIN>/<timestamp>-<prefix>/`), and
  flash-history records sync to the workstation over 2.5GbE or by NVMe
  hot-swap ([Section 2, Step 3](#step-3--nvme-storage-array)).
- The workstation runs firmware unpacking / disassembly
  ([Section 3](#3-software-build-steps)) and writes new calibration
  catalog entries back into `calibrations/<ECU>/`.

### 1.5 Full PC → Cloud

- `rclone sync` pushes `calibrations/` and `logs/` to a Google Drive
  remote on a schedule; `src/cloud/sync.py`'s `OfflineCache` /
  `CloudSyncClient` handle the structured-data half (VIN profiles, DTC
  history, flash history) against `backend/app`, while rclone handles
  the bulk binary archive (firmware images, full session captures) that
  doesn't belong in the SQL-shaped backend. See
  [Section 16](#16-cloud-architecture).

---

## 2. Hardware build steps

### Step 1 — Raspberry Pi 5 automotive interface

1. **OS install.** Flash Raspberry Pi OS Lite (64-bit, Bookworm) via
   `rpi-imager`; enable SSH and set hostname (e.g. `saabpi`) in the
   imager's advanced options so first boot is headless.
2. **CAN interface.** Use a CAN HAT with an MCP2515 controller + TJA1050
   transceiver (SPI, up to 1 Mbps — sufficient for 500 kbps HS-CAN) or a
   Waveshare/PiCAN2 board. Enable it in `/boot/firmware/config.txt`:
   ```ini
   dtparam=spi=on
   dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=25
   dtoverlay=spi-bcm2835
   ```
   Bring the interface up with SocketCAN:
   ```bash
   sudo ip link set can0 up type can bitrate 500000
   ```
3. **LIN wiring.** LIN has no native Pi HAT ecosystem as mature as CAN;
   use a UART-to-LIN transceiver (e.g. TJA1027/MCP2003) on GPIO14/15
   (UART TXD/RXD) — see [Section 7](#7-wiring-diagrams) for pinout.
4. **Cooling.** Official Active Cooler (PWM fan + heatsink) on the PoE+/
   fan header; automotive under-dash/glovebox mounting runs warmer than
   a desk, so don't skip active cooling even for Lite (headless) images —
   sustained CAN capture plus logging is a real, non-bursty CPU/IO load.
5. **Python automotive libraries.**
   ```bash
   sudo apt install python3-pip can-utils
   python3 -m pip install python-can cantools pyserial
   ```
   `python-can`'s `socketcan` backend talks directly to the `can0`
   interface from step 2; `src/can/bus.py` wraps it for SAAB-SUITE's own
   use.

### Step 2 — Mini Windows PC (Intel N100)

1. **Windows 11 install.** Standard OOBE install (IoT Enterprise or Pro,
   whichever license you hold); disable unneeded background services
   (Xbox, widgets) to keep the N100's limited cores free for the OEM
   tool + J2534 bridge.
2. **OEM diagnostic suite.** Install only the suites you're licensed
   for, following each vendor's own installer (Techstream, ISTA, ODIS,
   GM SPS/ACDelco TDS, Ford FMP, Honda HDS). These are unrelated,
   separately-licensed products — this blueprint doesn't standardize
   their install process beyond "follow the vendor's own instructions
   and licensing."
3. **J2534 driver installation.** Install the custom bridge driver
   ([Section 8](#8-j2534-driver-emulation)) so it registers under
   `HKLM\SOFTWARE\PassThruSupport.04.04\<VendorName>` exactly like a
   commercial J2534 device — this is the standard registration point
   every J2534 application (including the OEM tools above) scans, per
   the SAE J2534-1 spec. `src/j2534/interface.py::_test_windows()`
   already reads this same registry path for self-test.
4. **Custom interface software.** The calibration-selector + flash-safe
   client from [Section 3](#3-software-build-steps), packaged as a
   Windows service so it starts before a technician opens the OEM tool.

### Step 3 — NVMe storage array

1. **Multi-drive configuration.** Two NVMe drives in the workstation:
   one fast scratch drive for active firmware-analysis work, one larger
   archive drive for the calibration library + full session-log history.
   RAID is unnecessary here (the archive's durability comes from cloud
   sync, not local redundancy) — keep it as two independent volumes to
   avoid a single controller/array fault taking out both roles at once.
2. **Calibration archive folder structure:**
   ```
   /archive/calibrations/<ECU>/<cal_id>.json      # mirrors calibrations/<ECU>/
   /archive/calibrations/<ECU>/index.json
   /archive/firmware/<ECU>/<cal_id>/dump.bin       # full binary, not in git
   /archive/firmware/<ECU>/<cal_id>/dump.sha256
   /archive/logs/<VIN>/<timestamp>-<prefix>/       # mirrors logs/<VIN>/...
   ```
   Keep binary firmware dumps out of the git repo entirely (they're
   large, and per the security-access disclaimer this project doesn't
   redistribute manufacturer firmware) — the archive volume and its
   rclone remote are the actual store of record for binaries; the repo
   only stores the JSON metadata schema shape.
3. **rclone sync setup.**
   ```bash
   rclone config create gdrive drive
   rclone sync /archive/calibrations gdrive:saab-suite/calibrations --transfers 4
   rclone sync /archive/logs gdrive:saab-suite/logs --transfers 4 --max-age 90d
   ```
   Schedule via `cron` (Linux) or Task Scheduler (Windows) — see
   [Section 16](#16-cloud-architecture) for retention/versioning policy.

### Step 4 — Full PC workstation (ROG Strix)

1. **Build.** Standard ATX build on a ROG Strix board; no automotive-
   specific hardware requirement here beyond enough PCIe lanes for two
   NVMe drives and a discrete GPU if you intend to run VMs with GPU
   passthrough for a Windows OEM-tool VM alongside Linux RE tools.
2. **OS.** Either bare-metal Linux (Ubuntu/Debian) with Windows in a VM
   for any Windows-only RE tooling, or bare-metal Windows with WSL2 for
   Linux-only tools — pick based on which side (RE tools vs. OEM tools)
   you use more often, since that's the side you want bare-metal
   performance on.
3. **Reverse-engineering tools.** Ghidra or IDA Free/Pro for ECU binary
   disassembly, `binwalk` for firmware-image unpacking, a hex editor
   (ImHex/010 Editor), and Python (`capstone`, `unicorn`) for scripted
   analysis. See [Section 3](#3-software-build-steps).
4. **VM environments.** A Windows 11 VM (VMware/Proxmox/Hyper-V) mirrors
   the Mini PC's OEM-tool environment for offline analysis of captured
   sessions without touching the vehicle-connected Mini PC.

---

## 3. Software build steps

### Raspberry Pi software

| Module | Repo location | Role |
|---|---|---|
| CAN bus listener | `src/can/bus.py`, `src/sniffer/engine.py` | SocketCAN frame capture, ring-buffer + file sink |
| Calibration ID parser | `src/uds/client.py` + `src/ecu/trionic8.py` DID map | Reads `0xF1A2`/`0xF187`/`0xF197` via UDS `ReadDataByIdentifier` |
| VIN decoder | `src/vin/decoder.py` | WMI/VDS/VIS decode, model-year table |
| Data forwarder | `src/remote/client.py` | Pushes capture summaries to Mini PC / backend over the WebSocket schema in `backend/app/websocket_remote.py` |
| Logging + timestamping | `src/logging/session.py` | VIN-tagged session directories under `logs/` |

New glue code needed: a small `pi_agent.py` that on boot brings up
`can0`, runs `J2534Device.probe_all_protocols()` once per new vehicle
connection (detected via CAN activity, not a button press), and streams
the metadata bundle to the Mini PC's calibration-selector endpoint.
Model it directly on `docs/ecosystem-architecture.md`'s documented
auto-detection pipeline (`src/j2534/simulator.py` →
`src/vin/decoder.py` → `src/calibration/catalog.py`) — that pipeline
already exists and is tested; the agent just needs to run it
unattended and forward the result.

### Mini PC software

| Module | Repo location | Role |
|---|---|---|
| J2534 pass-through interface | New: `windows/j2534-bridge/` | Implements SAE J2534-1/-2 API over the custom hardware — see [Section 8](#8-j2534-driver-emulation) |
| Calibration file selector | `src/calibration/catalog.py` (run on Mini PC against the mirrored archive) | VIN → applicable cal_id → dependency order |
| Flashing safety system | `src/flashsafe/checklist.py`, `src/flashing/engine.py` | Gates every write — see [Section 10](#10-firmware-flashing-safety-system) |
| Cloud sync client | `src/cloud/sync.py` against `backend/app` | Structured metadata sync (VIN profiles, DTC/flash history) |
| OEM diagnostic tools | Vendor-installed, unmodified | Talk to the J2534 bridge like any certified interface |

### Full PC software

| Module | Tooling | Role |
|---|---|---|
| Firmware unpacking | `binwalk`, custom Python (Motorola S-record / Intel HEX parsers for T8 BIN dumps) | Split combined dumps into OS/CAL/BOOT segments matching `CalibrationRecord.segment_type` |
| Reverse-engineering suite | Ghidra (with a Bosch ME-family processor module if targeting the underlying 68HC12/MPC5xx core), IDA | Static analysis of unpacked segments |
| Calibration database builder | `src/calibration/catalog.py` (authoring side: writes new `CalibrationRecord` JSON) | Turns RE findings + dumps into catalog entries with `applicability`, `depends_on`, `supersedes` filled in |
| Cloud sync + backup | `rclone` + `src/cloud/sync.py` | Bulk binary sync + structured metadata sync, respectively |

---

## 4. Final assembly

```
┌──────────────────────────┐      ┌──────────────────────────┐      ┌──────────────────────────┐
│  1. Handheld unit         │      │  2. Windows flashing unit │      │  3. Dev workstation       │
│  Pi 5 + CAN/LIN HAT +     │◀────▶│  Mini PC (N100) +         │◀────▶│  ROG Strix + dual NVMe    │
│  enclosure                │ USB- │  J2534 bridge + OEM tools │ 2.5G │  + RE tool chain          │
│                            │ Eth  │                            │ LAN  │                            │
└────────────┬──────────────┘      └────────────┬──────────────┘      └────────────┬──────────────┘
             │ OBD-II / GPIO                     │ J2534 (shared bus)               │
             ▼                                   ▼                                  │
        ┌─────────┐                         ┌─────────┐                            │
        │ Vehicle │────────────────────────▶│ Vehicle │                            │
        └─────────┘                         └─────────┘                            │
                                                                                     ▼
                                                                          ┌──────────────────┐
                                                                          │  Cloud (Drive)     │
                                                                          └──────────────────┘
```

**Workflow:**

1. Technician connects the handheld unit (Pi 5) to the vehicle's OBD-II
   port. It auto-detects protocol, decodes VIN, reads calibration IDs,
   and streams the metadata bundle to the Mini PC over USB-Ethernet
   (works even with no shop Wi-Fi/LAN present).
2. The Mini PC's calibration-selector matches the metadata against its
   mirrored calibration archive and presents the technician a short list
   of applicable calibrations/updates inside the OEM tool's own UI (via
   the DID/PID data the J2534 bridge exposes) or a companion status
   window.
3. **Physical bus handoff:** the Pi 5 and Mini PC do not both hold the
   CAN transceiver at once. Either (a) the Pi 5's CAN HAT is the only
   physical connection, and the Mini PC's J2534 bridge talks to the Pi
   5 as its transport (Pi 5 relays raw CAN frames it isn't otherwise
   using — see [Section 8](#8-j2534-driver-emulation)), or (b) the OBD-II
   connector splits to two physical taps (Pi 5 CAN HAT + Mini PC's own
   USB-CAN dongle) and only one is active at a time, coordinated by a
   simple "who owns the bus" lock the pi_agent and bridge both check
   before transmitting. Option (a) is simpler and is the default this
   blueprint assumes.
4. The technician runs the licensed OEM tool on the Mini PC to execute
   the flash; `src/flashsafe/checklist.py` gates the write.
5. After the session, firmware dumps and logs sync to the workstation
   (LAN or NVMe hot-swap) for RE/calibration-database work, then to
   Google Drive via rclone.

---

## 5. Additional requirements

### Replicating Mongoose GM II Pro / VCX Nano *behavior* (not identity)

Build to the SAE J2534-1 (basic pass-through) and J2534-2 (OEM
extensions, e.g. GM's) API surface: `PassThruOpen`, `PassThruConnect`,
`PassThruReadMsgs`/`WriteMsgs`, `PassThruIoctl` (including
`SET_CONFIG`/`READ_VBATT`/`FIVE_BAUD_INIT`/`FAST_INIT`), and the
protocol channel IDs for CAN, ISO15765, ISO9141, ISO14230 (KWP2000), J1850 VPW/PWM.
Any OEM tool built against this open spec — GM's Tech2Win, TIS2000, GDS2,
generic scan tools — works against your device the moment the DLL is
registered, with zero vendor-specific spoofing.

### Tech2Win / TIS2000 integration

Both expect a registered J2534 DLL and, for GM flows specifically, GM's
own SPS/Techline security-access service for actual programming (outside
this project's scope per the disclaimer). Read-only diagnostics (DTCs,
live data, module IDs) work over the bridge with no OEM licensing
dependency beyond the tool itself; `src/emulator/tech2.py` already
models the Tech2/MDI request-response shape used for bench-testing the
bridge without a live GM vehicle attached.

### Saab 9-3 (9440) Bosch ME9.6 / Trionic T8 specifics

Already modeled in `src/ecu/trionic8.py`: HS-CAN 500 kbps, `0x7E0`/`0x7E8`
diagnostic IDs, the DID map (VIN, part number, serial, SW version, cal
fingerprint, and the ~15 live-data DIDs used for the B284R). Extend
`plugins/gm/` (Saab used GM's diagnostic backbone post-2000) with a
Trionic-specific plugin if you want it to go through the generic
`OEMPlugin` contract rather than being called directly.

### Calibration archive structure for future expansion

Keep the existing `calibrations/<ECU>/<cal_id>.json` + `index.json`
shape (it already generalizes across ECUs/OEMs) and add new top-level
`<ECU>` directories as you add platforms — no schema change needed for
EV/ADAS ECUs, just new DID maps and plugins. See
[Section 9](#9-calibration-database-system).

### Modularity / upgradability

The plugin architecture (`src/plugins/base.py`, `docs/plugin-api.md`)
is the extension point for new OEMs; the J2534 bridge is transport-
agnostic to what's above it (any J2534-compliant app), so upgrading the
Pi 5's CAN HAT, adding CAN-FD, or swapping the Mini PC for a different
mini-PC doesn't require touching the OEM-tool-facing API.

---

## 6. Optional expansions

- **EV/ADAS support:** add CAN-FD capable transceivers (e.g. MCP2518FD
  HAT instead of MCP2515) for higher-bandwidth ADAS buses, and new
  plugins/DID maps for BMS and radar/camera ECUs. The calibration
  catalog schema already supports arbitrary `ecu` values.
- **OTA firmware update system:** extend `backend/app` with a
  `routes_ota.py` that serves signed calibration bundles to registered
  Mini PC clients; reuse `src/cloud/sync.py`'s offline-cache pattern for
  download resumability.
- **Cloud-based calibration detection:** move `CalibrationCatalog`
  lookups server-side (`backend/app`) so new calibrations are available
  to every Mini PC/Pi pair immediately rather than waiting for the next
  rclone pull — the Pi 5 metadata bundle already carries everything a
  server-side lookup needs.
- **Multi-device ecosystem:** the WebSocket hub in
  `backend/app/websocket_remote.py` already supports multiple concurrent
  sessions; a fleet of handheld units reporting to one backend is a
  deployment change, not a new architecture.
- **Secure bootloader + anti-brick flashing:** see
  [Section 15](#15-bootloader-design) and
  [Section 10](#10-firmware-flashing-safety-system).

---

## 7. Wiring diagrams

### 7.1 Raspberry Pi 5 CAN bus wiring (MCP2515 HAT, SPI0)

```
Raspberry Pi 5 GPIO header (40-pin)          MCP2515/TJA1050 CAN HAT
┌─────────────────────────┐
│ 1  3V3          3V3  2  │
│ 3  SDA1          5V  4  │
│ 5  SCL1          GND  6 │
│ 7  GPIO4  (INT)  ---  8 │──── INT ───▶ GPIO25 (per dtoverlay above)
│ 9  GND          ...  10 │
│ 19 SPI0 MOSI ───────────┼───▶ SI
│ 21 SPI0 MISO ◀──────────┼──── SO
│ 23 SPI0 SCLK ───────────┼───▶ SCK
│ 24 SPI0 CE0  ───────────┼───▶ CS
│ 25 GND          ...     │
└─────────────────────────┘

CAN HAT terminal block → OBD-II connector (J1962):
  CAN-H  ──────────────▶  Pin 6
  CAN-L  ──────────────▶  Pin 14
  GND    ──────────────▶  Pin 4 or 5
  (Pin 16 = +12V, battery — power the Pi via a separate buck converter,
   not directly off Pin 16, per Section 7.4.)
```

| HAT pin | Signal | Pi 5 pin | Notes |
|---|---|---|---|
| VCC | 5V | Pin 2/4 | HAT logic supply |
| GND | GND | Pin 6/9/14/20/25/30/34/39 | Common ground, keep short |
| SI/SO/SCK | SPI0 MOSI/MISO/SCLK | Pin 19/21/23 | Standard SPI0 |
| CS | SPI0 CE0 | Pin 24 | `dtoverlay=mcp2515-can0` default |
| INT | GPIO25 | Pin 22 | Must match `interrupt=` overlay param |

### 7.2 LIN bus GPIO wiring (UART + TJA1027 transceiver)

```
Pi 5 GPIO14 (TXD) ──▶ TJA1027 TXD
Pi 5 GPIO15 (RXD) ◀── TJA1027 RXD
Pi 5 3V3          ──▶ TJA1027 VIO
Pi 5 5V           ──▶ TJA1027 VBAT (if module needs 5-12V rail — check datasheet)
Pi 5 GND          ──▶ TJA1027 GND
TJA1027 LIN pin   ──▶ Vehicle LIN bus (single wire, master pull-up to VBAT per LIN spec)
```

Disable the Pi's default serial console on `/dev/ttyAMA0` before use
(`raspi-config` → Interface Options → Serial Port → login shell: No,
hardware enabled: Yes) — otherwise the getty process fights your LIN
driver for the UART.

### 7.3 USB-CAN adapter integration (alternative to SPI HAT)

```
Pi 5 USB3 port ──▶ USB-CAN adapter (e.g. CANable, PEAK PCAN-USB) ──▶ OBD-II CAN-H/L
```
Appears as `can0`/`can1` via `gs_usb`/`slcan` kernel driver — no
device-tree overlay needed; `ip link set can0 up type can bitrate 500000`
works identically to the HAT path. Preferred when you want the same
enclosure to also plug into the Mini PC directly (swap which host owns
the dongle) without re-wiring GPIO.

### 7.4 Power distribution

```
Vehicle 12V (OBD-II pin 16 or dedicated fused tap)
        │
        ▼
  ┌───────────────┐
  │ Automotive-    │  (wide input range, load-dump/reverse-polarity
  │ grade buck     │   protected — e.g. Pololu D24V50F5 or similar
  │ converter      │   automotive buck, NOT a generic phone charger)
  │ 12V → 5V/5A    │
  └───────┬───────┘
          │ USB-C PD or GPIO 5V/GND
          ▼
   Raspberry Pi 5 (5V/5A via USB-C, official PSU behavior)
```

| Rail | Source | Consumer | Notes |
|---|---|---|---|
| 12V (vehicle) | OBD-II pin 16 or fused accessory tap | Buck converter input | Fuse at the tap, not just at the converter |
| 5V/5A | Buck converter output | Pi 5 (USB-C) | Pi 5 draws up to ~5A under CAN+active-cooling load with HAT attached |
| 3.3V | Pi 5 GPIO header | CAN HAT logic | Regulated on-HAT typically; confirm HAT doesn't backfeed 3V3 rail beyond Pi's budget |

### 7.5 Enclosure layout (see Section 12 for full mechanical detail)

```
┌───────────────────────────────────────────┐
│  [Status LEDs]      TOP PANEL              │
│                                              │
│  ┌────────────┐   ┌──────────────┐         │
│  │ Pi 5 + HAT │   │ Active cooler │         │
│  └────────────┘   └──────────────┘         │
│                                              │
│  [OBD-II pigtail]   [USB-C power in]       │
│  [USB-Eth to Mini PC]                       │
└───────────────────────────────────────────┘
```

### 7.6 Cable routing

- Keep CAN-H/CAN-L as a twisted pair end-to-end (HAT terminal block →
  OBD-II pigtail) — untwisting even a few cm to reach terminal-block
  screws degrades noise immunity on a bus that's already sharing an
  underhood/underdash environment with ignition coils and injectors.
- Route power and signal cables on opposite sides of the enclosure
  interior where the layout allows it, to reduce injected switching
  noise from the buck converter onto the SPI/CAN lines.

---

## 8. J2534 driver emulation

### 8.1 Goal

Present a standards-conformant J2534-1/-2 pass-through DLL (`.dll` on
Windows, matching `PassThruOpen`/`Close`/`Connect`/`Disconnect`/
`ReadMsgs`/`WriteMsgs`/`StartPeriodicMsg`/`StopPeriodicMsg`/
`StartMsgFilter`/`StopMsgFilter`/`Ioctl`/`ReadVersion`/`GetLastError`)
that any J2534-aware application can load, so OEM tools work against
custom hardware exactly as they would against a certified commercial
device — without redistributing or mimicking any specific vendor's
identity.

### 8.2 Architecture

```
┌──────────────────────────────────────────────────────────┐
│  OEM tool (Tech2Win / TIS2000 / GDS2 / generic J2534 app) │
└───────────────────────────┬────────────────────────────────┘
                             │ standard J2534 DLL calls
                             ▼
┌──────────────────────────────────────────────────────────┐
│  j2534_bridge.dll  (this project)                          │
│   - API surface: PassThruOpen/Connect/Read/Write/Ioctl/... │
│   - Protocol state machines: CAN, ISO15765, ISO9141,        │
│     ISO14230 (KWP2000), J1850 VPW/PWM                       │
│   - Channel manager (multi-channel, filters, periodic msgs)│
└───────────────────────────┬────────────────────────────────┘
                             │ transport (USB/serial/TCP to Pi 5
                             │ or a dedicated MCU front-end)
                             ▼
┌──────────────────────────────────────────────────────────┐
│  Hardware front-end (Pi 5 CAN HAT / MCU + CAN transceiver) │
│   - Frame TX/RX, hardware filtering, bus-off recovery       │
└──────────────────────────────────────────────────────────┘
```

### 8.3 Pseudocode — core API shape

```c
// j2534_bridge.h — matches the public SAE J2534-1 signatures
long PTAPI PassThruOpen(void *pName, unsigned long *pDeviceID);
long PTAPI PassThruClose(unsigned long DeviceID);
long PTAPI PassThruConnect(unsigned long DeviceID, unsigned long ProtocolID,
                            unsigned long Flags, unsigned long Baudrate,
                            unsigned long *pChannelID);
long PTAPI PassThruDisconnect(unsigned long ChannelID);
long PTAPI PassThruReadMsgs(unsigned long ChannelID, PASSTHRU_MSG *pMsgs,
                             unsigned long *pNumMsgs, unsigned long Timeout);
long PTAPI PassThruWriteMsgs(unsigned long ChannelID, PASSTHRU_MSG *pMsgs,
                              unsigned long *pNumMsgs, unsigned long Timeout);
long PTAPI PassThruStartPeriodicMsg(unsigned long ChannelID, PASSTHRU_MSG *pMsg,
                                     unsigned long *pMsgID, unsigned long Interval);
long PTAPI PassThruStartMsgFilter(unsigned long ChannelID, unsigned long FilterType,
                                    PASSTHRU_MSG *pMaskMsg, PASSTHRU_MSG *pPatternMsg,
                                    PASSTHRU_MSG *pFlowControlMsg, unsigned long *pFilterID);
long PTAPI PassThruIoctl(unsigned long ChannelID, unsigned long IoctlID,
                          void *pInput, void *pOutput);
```

```c
// PassThruConnect: maps ProtocolID to the hardware front-end's channel manager
long PTAPI PassThruConnect(unsigned long DeviceID, unsigned long ProtocolID,
                            unsigned long Flags, unsigned long Baudrate,
                            unsigned long *pChannelID) {
    if (!device_is_open(DeviceID)) return ERR_INVALID_DEVICE_ID;
    Channel *ch = channel_alloc();
    switch (ProtocolID) {
        case ISO15765: ch->codec = &iso15765_codec; break;   // ISO-TP over CAN
        case CAN:       ch->codec = &raw_can_codec;   break;
        case ISO9141:   ch->codec = &kline_5baud_codec; break;
        case ISO14230:  ch->codec = &kwp2000_codec;    break;
        case J1850VPW:  ch->codec = &vpw_codec;        break;
        case J1850PWM:  ch->codec = &pwm_codec;        break;
        default: channel_free(ch); return ERR_INVALID_PROTOCOL_ID;
    }
    ch->baudrate = Baudrate;
    hw_configure(ch);              // sends config down to Pi5/MCU front-end
    *pChannelID = ch->id;
    return STATUS_NOERROR;
}
```

### 8.4 ISO-TP / CAN-FD / K-Line / VPW / PWM handling

| Protocol | Handling |
|---|---|
| ISO-TP (ISO15765) | Segment/reassemble per ISO 15765-2: single frame (SF), first frame (FF)/consecutive frame (CF) with flow control (FC) — implement as a small state machine per channel, `wait_fc → send_cf → done`, honoring `BS` (block size) and `STmin` from the FC frame |
| CAN-FD | Requires an MCP2518FD-class controller front-end instead of MCP2515 (classic CAN only does 8-byte frames); expose as a separate `ProtocolID` (`CAN_PS` in J2534 v04.04) |
| K-Line (ISO9141/ISO14230) | 5-baud or fast init per `PassThruIoctl(FIVE_BAUD_INIT / FAST_INIT)`; needs a K-Line transceiver (e.g. L9637) on the front-end, not the CAN transceiver |
| J1850 VPW/PWM | Legacy GM (VPW)/Ford (PWM) — only relevant for pre-CAN vehicles; needs a dedicated VPW/PWM transceiver, out of scope for the 2008 Saab (CAN-only) but included for completeness/future platforms |

### 8.5 GM SPS / Tech2Win / TIS2000 support

These applications use the standard `PassThruConnect(ISO15765, ...)` /
`PassThruIoctl` surface for the diagnostic-session and read/write-data
portions; GM's actual programming/security-access flow additionally
calls out to GM's own licensed SPS/Techline backend, which this bridge
does not (and cannot legally) implement — see the scope boundary at the
top of this document.

---

## 9. Calibration database system

### 9.1 Schema (extends `src/calibration/catalog.py`'s `CalibrationRecord`)

```
CalibrationRecord
├── cal_id            (PK within an ECU directory)
├── os_id
├── calibration_id
├── cvn
├── segment_type       (OS | CAL | BOOT | STRATEGY)
├── ecu                (e.g. "T8", future: "BMS", "ADAS_FC")
├── applicability[]    (VIN / WMI-VDS prefixes)
├── depends_on[]        (other cal_ids required first)
├── supersedes          (previous cal_id in the update chain)
├── release_date
└── notes
```

```
calibrations/
├── T8/
│   ├── index.json          # [{cal_id, calibration_id, ...summary}, ...]
│   ├── CAL0001.json
│   └── CAL0002.json
└── <future ECU>/
    ├── index.json
    └── ...
```

### 9.2 Workflows

- **VIN-based lookup:** `CalibrationCatalog.lookup_by_vin(vin)` scans
  every ECU's index and matches `applicability` patterns
  (`_vin_matches`) — exact VIN or WMI/VDS prefix.
- **Dependency resolution:** `resolve_dependencies(ecu, cal_id)` performs
  a DFS topological sort over `depends_on`, raising on cycles — this is
  what turns "flash CAL0002" into "flash BOOT0001, then OS0001, then
  CAL0002" when CAL0002 depends on a newer OS.
- **Flash compatibility:** `check_flash_compatibility(ecu, cal_id,
  current_os_id)` compares the catalog's expected `os_id` against what
  the ECU currently reports (read live via DID `0xF1A2`/`0xF197`) —
  this is the check `src/flashsafe/checklist.py`'s
  `calibration_file_valid` field is populated from.
- **Metadata extraction (new, workstation-side):** after unpacking a
  firmware dump, a small extractor script derives `os_id`/`cvn` from the
  known offset/checksum fields the RE work identifies, and drafts a
  `CalibrationRecord` for technician review before it's committed to
  `calibrations/<ECU>/`.
- **rclone sync:** the JSON metadata under `calibrations/` is small and
  git-trackable; treat it as the source of truth synced by `git`
  between developers and by `rclone` to the Drive archive for field
  units that don't run git directly.
- **Future expansion (EV/ADAS):** add `ecu` values like `BMS`, `ADAS_FC`,
  `INV` (inverter) — the schema needs no change; only new plugins/DID
  maps are required per [Section 5](#5-additional-requirements).

---

## 10. Firmware flashing safety system

### 10.1 Flowchart

```
                     ┌─────────────────────┐
                     │ Technician initiates │
                     │ flash request         │
                     └──────────┬───────────┘
                                ▼
                  ┌───────────────────────────┐
                  │ FlashSafeChecklist.evaluate│
                  │ (src/flashsafe/checklist.py│
                  └──────────┬────────────────┘
                              │
             ┌────────────────┼─────────────────────┐
             ▼                ▼                      ▼
     battery > 12.4V?   ignition ON?          CAN bus stable?
             │                │                      │
             ▼                ▼                      ▼
     J2534 buffers OK?  programming session?   no blocking DTCs?
             │                │                      │
             └────────┬───────┴──────────┬───────────┘
                       ▼                  ▼
              calibration file valid  (CVN/OS-ID match vs. catalog)
                       │
                       ▼
              ┌─────────────────┐   FAIL/UNKNOWN on any check
              │ all_clear()?     │──────────────────────────▶ ABORT, log failures,
              └────────┬─────────┘                             surface to technician
                       │ PASS
                       ▼
             ┌───────────────────────┐
             │ Backup current image   │  (full read-before-write,
             │ (checksum + store)     │   stored under archive/firmware/)
             └──────────┬─────────────┘
                        ▼
             ┌───────────────────────┐
             │ FlashSession.start()   │  (src/flashing/engine.py)
             │  - security access     │  (fails closed w/o real
             │    (NullSeedKeyProvider│   SeedKeyProvider — see
             │    raises if unset)    │   docs/security-access-disclaimer.md)
             │  - block transfer +    │
             │    flow control        │
             │  - resume-safe          │
             │    checkpointing        │
             └──────────┬─────────────┘
                        ▼
           ┌─────────────────────────┐
           │ Voltage monitored          │──▶ drop below threshold mid-flash
           │ continuously during write  │      → pause/abort per Section 10.3
           └──────────┬─────────────────┘
                        ▼
              ┌───────────────────┐
              │ Verify write        │  (read-back checksum vs. expected CVN)
              └──────────┬─────────┘
                        ▼
             success ──▶ log to flash_history, sync to backend
             failure ──▶ enter recovery mode (Section 15) + log

```

### 10.2 Pre-flash validation (already implemented)

`FlashSafeChecklist` enforces all seven checks in
`src/flashsafe/checklist.py` before `FlashSession.start()` proceeds;
`FlashSession` additionally refuses to continue if the `SeedKeyProvider`
in use is the default `NullSeedKeyProvider`, so an unconfigured system
fails closed rather than sending a garbage key.

### 10.3 Voltage monitoring during the write itself

Extend `VehicleState.battery_voltage` from a one-time pre-flash reading
to a polled value during the write (every block-transfer ACK is a
natural poll point given UDS's transfer-data cadence). If voltage drops
below `MIN_BATTERY_VOLTAGE` (12.4V) mid-write:

1. Pause at the next safe block boundary (never mid-block).
2. Prompt for a battery charger/maintainer to be connected.
3. Resume from the last confirmed block (this is what "resume-safe
   checkpointing" in `FlashSession` is for) rather than restarting from
   block 0.

### 10.4 Backup & restore

Read-before-write: dump the full current image (all segments the flash
touches) and store it under `archive/firmware/<ECU>/<cal_id>/dump.bin`
with a `dump.sha256` alongside, before any write begins. Restore is the
same `FlashSession` machinery run in reverse (backup image as the
"target").

### 10.5 Anti-brick recovery mode

See [Section 15](#15-bootloader-design) — recovery mode is a bootloader
property (a minimal, unbrickable first-stage loader that can always
accept a re-flash of the application image, independent of whether the
application image itself is corrupt).

### 10.6 Logging & rollback

Every flash attempt — success or failure — writes a `flash_history` row
(`ecu`, `cal_id`, `result`, `recorded_at`, full block-level log as
`payload`) via `src/cloud/sync.py::OfflineCache.upsert()`, syncing to
`backend/app` when connectivity allows. Rollback is: look up the prior
`cal_id` via `CalibrationCatalog.update_history()`'s `supersedes` chain,
and re-run `FlashSession` against that record (or the raw backup image
from 10.4 if the prior record isn't in the catalog).

---

## 11. Hardware bill of materials

Prices are rough 2026 street-price ranges (USD), not quotes — confirm
current pricing before ordering. "Alt." = a functionally interchangeable
alternative.

### 11.1 Raspberry Pi automotive interface

| Part | Example / part number | Qty | Est. cost | Alt. |
|---|---|---|---|---|
| Raspberry Pi 5 (8GB) | SC1112 | 1 | $80 | 4GB variant, $60 |
| Official Active Cooler | SC1148 | 1 | $5 | Third-party heatsink+fan |
| microSD / NVMe boot media | SanDisk Extreme 64GB / Pi NVMe HAT + M.2 SSD | 1 | $15–45 | — |
| CAN HAT (MCP2515+TJA1050) | Waveshare RS485 CAN HAT, or PiCAN2 | 1 | $25–45 | USB-CAN dongle (CANable 2.0, ~$30) instead of HAT |
| LIN transceiver breakout | TJA1027/MCP2003-based breakout | 1 | $10–20 | Omit if no LIN modules targeted |
| OBD-II pigtail cable | J1962 male pigtail, 6+ wire | 1 | $8–15 | — |
| Automotive buck converter (12V→5V/5A) | Pololu D24V50F5 or equivalent automotive-rated buck | 1 | $15–25 | Do not substitute a generic USB car charger — no load-dump protection |
| Inline fuse holder + fuse | ATC mini fuse holder, 3A | 1 | $5 | — |
| Enclosure | See Section 12 | 1 | $20–60 | — |

**Subtotal:** ≈ $183–295

### 11.2 Mini PC flashing unit

| Part | Example | Qty | Est. cost | Alt. |
|---|---|---|---|---|
| Intel N100 mini-PC | "Mini PC Pro 2"-class N100 box, 16GB/512GB | 1 | $150–220 | Any N100/N150 mini-PC with 2× USB3 + Ethernet |
| USB-CAN dongle (if not relaying via Pi) | PEAK PCAN-USB, CANable 2.0 | 1 | $30–200 | — |
| USB-Ethernet adapter (gadget-mode link to Pi) | Any USB3 GbE adapter | 1 | $12–20 | Use onboard NIC + a small switch instead |

**Subtotal:** ≈ $192–440

### 11.3 Full PC workstation

| Part | Example | Qty | Est. cost | Alt. |
|---|---|---|---|---|
| Motherboard | ROG Strix B650-A / Z790-A | 1 | $200–300 | Any ATX board w/ 2× M.2 |
| CPU | Ryzen 7 / Core i5-i7 current-gen | 1 | $250–400 | — |
| RAM | 32–64GB DDR5 | 1 kit | $100–200 | — |
| NVMe (scratch) | 1TB Gen4 NVMe | 1 | $70–100 | — |
| NVMe (archive) | 2–4TB Gen4 NVMe | 1 | $130–250 | — |
| GPU (optional, for VM passthrough) | Any current mid-range | 1 | $250+ | Skip if no GPU-accelerated RE workload |
| PSU | 650–750W 80+ Gold | 1 | $80–120 | — |
| Case + cooling | ROG Strix-series case, tower air cooler | 1 | $120–200 | — |

**Subtotal:** ≈ $1,200–1,860 (excluding optional GPU)

### 11.4 CAN/LIN adapters, power distribution, enclosure components (shared)

| Part | Example | Qty | Est. cost |
|---|---|---|---|
| Twisted-pair CAN cable | 22AWG twisted pair, automotive-rated | few meters | $5–10 |
| 120Ω termination resistors | Standard through-hole, if building a bench CAN network | 2 | $1 |
| Enclosure standoffs/screws | M2.5/M3 nylon standoff kit | 1 kit | $8 |
| Cable glands | PG7/PG9 | few | $5 |
| Status LEDs + resistors | 3mm/5mm LED assortment | few | $3 |

---

## 12. Enclosure design

### 12.1 Mechanical layout (handheld Pi 5 unit)

```
                     TOP VIEW (lid removed)
        ┌───────────────────────────────────────────┐
        │  ┌───────────────┐        ┌─────────────┐  │
        │  │  Pi 5 board    │        │ Active      │  │
        │  │  (mounted on    │        │ Cooler       │  │
        │  │   4x M2.5        │        │ (fan intake  │  │
        │  │   standoffs)     │        │  from top)   │  │
        │  └───────────────┘        └─────────────┘  │
        │                                               │
        │  ┌────────────┐                              │
        │  │ CAN HAT     │  (stacked on Pi GPIO header) │
        │  └────────────┘                              │
        │                                               │
        │  [LIN breakout, if used] ── flying leads      │
        │                                               │
        └──────────┬──────────────┬──────────┬──────────┘
                    │              │           │
              OBD-II pigtail   USB-C pwr   USB-Eth (to Mini PC)
                    (side panel cutouts, cable glands)
```

- **Dimensions:** ~120mm × 90mm × 40mm internal, sized around the Pi 5 +
  HAT stack + Active Cooler height (the cooler is the tallest component
  at ~25mm above the board).
- **Airflow:** Active Cooler draws air in from the top vent and exhausts
  through side vents at board level; orient the enclosure so the top
  vent isn't the surface resting in a technician's hand or a bag.
- **Mounting points:** 4× M2.5 standoffs at the Pi 5's official mounting-
  hole pattern (test points call this out on the official mechanical
  drawing); HAT stacks via the GPIO header + its own standoffs to the
  same plate.
- **Cable routing:** side-panel cutouts with cable glands for OBD-II
  pigtail, USB-C power, and USB-Ethernet — keep the CAN twisted pair's
  transition from HAT terminal block to the OBD-II pigtail as short and
  undisturbed as the enclosure geometry allows (see Section 7.6).
- **Material:** 3D-printed PETG (better heat tolerance than PLA for a
  glovebox/underdash environment) or a stock ABS project box
  (Hammond 1591-series) machined for the cutouts above — PETG is the
  better default if you're printing rather than machining, since
  under-dash temperatures can exceed PLA's ~60°C softening point on a
  hot day.

### 12.2 Full technical drawing note

Produce the actual mechanical drawing in a CAD tool (FreeCAD/Fusion 360)
from this layout — the ASCII sketch above is a floor-plan reference for
component placement and airflow direction, not a dimensioned drawing.

---

## 13. CAN/LIN protocol decoding

### 13.1 CAN frame decoding

Standard 11-bit CAN 2.0A frame relevant to OBD-II/UDS:

```
| SOF | ID (11b) | RTR | Control | Data (0-8B) | CRC | ACK | EOF |
```

For the T8: request ID `0x7E0`, response ID `0x7E8` (physical
addressing); functional broadcast is `0x7DF` per SAE J1979/ISO 15765-4.

### 13.2 ISO-TP segmentation (multi-frame UDS responses)

```
First Frame (FF):        [1 nibble=0x1][12-bit length][data 0..5]
Consecutive Frame (CF):  [1 nibble=0x2][4-bit seq 0-15][data 0..6]
Flow Control (FC):       [1 nibble=0x3][FS][BS][STmin]
```

Example: reading DID `0xF190` (VIN, 17 bytes) needs FF + 3×CF, with the
requester sending one FC after the FF to authorize the CF burst.

### 13.3 Extracting calibration IDs

1. Send `0x02 0x09 0x02` (Mode 09, PID 02 = VIN) to `0x7DF`, decode via
   `src/vin/decoder.py`.
2. Send `0x03 0x22 0xF1 0xA2` (ReadDataByIdentifier, DID `0xF1A2` =
   calibration fingerprint) to `0x7E0`, parse response `0x62 0xF1 0xA2
   <data>` from `0x7E8`.
3. Repeat for `0xF187` (part number), `0xF197` (SW version) to build the
   full identification tuple the calibration catalog matches against.

### 13.4 Module address identification

On the Saab's GM-derived backbone, module presence is enumerated by
functional-addressed requests (`0x7DF`) and noting which physical IDs
respond — `src/j2534/simulator.py::probe_all_protocols()` plus a sweep
of known physical ID pairs (`0x7E0/7E8` engine, and platform-specific
IDs for TCU/ABS/BCM modules) builds the module map.

### 13.5 LIN message decoding

```
| Break | Sync (0x55) | PID (6-bit ID + 2 parity) | Data (0-8B) | Checksum |
```

LIN has no ISO-TP equivalent — messages are single-frame only, addressed
by PID rather than by CAN-style arbitration ID; a LIN description file
(LDF) for the target modules gives the PID→signal mapping.

### 13.6 Example decode table (T8 live data, from `src/ecu/trionic8.py`)

| DID | Name | Raw scale | Decoded example |
|---|---|---|---|
| `0x2001` | Boost (kPa) | raw × 0.1 | `1523` → 152.3 kPa |
| `0x2003` | Coolant (°C) | raw × 0.1 − 40 | `1130` → 73.0 °C |
| `0x2008` | Lambda | raw × 0.01 | `98` → 0.98 |
| `0x200C` | Battery (V) | raw × 0.1 | `132` → 13.2 V |

---

## 14. PCB design

A custom PCB is optional (the HAT + breakout approach in Sections 2/7
is buildable without one) but worthwhile if producing more than a
handful of units. Outline for a "Pi 5 CAN/LIN carrier HAT":

### 14.1 Block schematic

```
┌──────────────────────────────────────────────────────────┐
│  40-pin GPIO connector (to Pi 5)                            │
└───────┬───────────────┬───────────────┬─────────────────┘
        │ SPI0            │ UART            │ 5V/3V3/GND
        ▼                 ▼                 ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────────┐
│ MCP2515 CAN    │  │ TJA1027 LIN    │  │ Power regulation   │
│ controller      │  │ transceiver     │  │ (3V3 LDO from 5V,   │
│ + TJA1050       │  │                 │  │  reverse-polarity   │
│ transceiver     │  │                 │  │  + TVS protection)  │
└───────┬───────────┘  └───────┬───────────┘  └───────────────────┘
        │                     │
        ▼                     ▼
   CAN-H/CAN-L            LIN + GND
   terminal block         terminal block
```

### 14.2 Layer stackup

4-layer, 1.6mm standard:

1. **Top** — signal + component placement
2. **Inner 1** — GND plane (unbroken under CAN/LIN traces for return-path
   integrity)
3. **Inner 2** — 3V3/5V power plane
4. **Bottom** — signal + secondary component placement (connectors)

### 14.3 Routing strategy

- Route CAN-H/CAN-L as a matched-length differential pair, 120Ω
  differential impedance target, away from the SPI clock trace to avoid
  crosstalk into the SPI bus.
- Keep the MCP2515 crystal/oscillator loop short and away from the CAN
  transceiver's board edge.
- Star-ground the analog/transceiver section back to a single point on
  the GND plane rather than daisy-chaining ground returns.

### 14.4 Component placement

- CAN/LIN transceivers near the board edge closest to the terminal
  blocks (shortest bus-side trace run).
- ESD/TVS diodes immediately at the terminal block, before the trace
  reaches the transceiver IC.
- MCP2515 + crystal centrally located, SPI traces length-matched and
  short.

### 14.5 ESD protection

Bidirectional TVS diode array (e.g. PESD1CAN or similar automotive-
rated CAN ESD protection part) across CAN-H/CAN-L at the terminal
block; a general-purpose TVS array on the LIN line and on the 5V input
rail (load-dump events are a real automotive-environment hazard even
downstream of the buck converter in Section 7.4).

### 14.6 Manufacturing notes

- Standard 2-layer is workable if cost-sensitive and you accept looser
  impedance control; 4-layer is recommended for any run beyond
  prototype quantities.
- Use HASL or ENIG finish; ENIG is worth the small upcharge if the board
  will see repeated connector mating cycles.
- Panelize for fab (most fabs quote per-panel, not per-board) if
  ordering more than ~10 units — see [Section 17](#17-manufacturing--supply-chain).

---

## 15. Bootloader design

### 15.1 Scope

Two distinct bootloader contexts:

1. **Raspberry Pi 5** — its boot chain (EEPROM bootloader → `bootcode`
   → kernel) is fixed silicon/firmware from Raspberry Pi; this project
   doesn't replace it, only configures boot order and (optionally)
   signs the OS image via the Pi's existing secure-boot support
   (`rpi-eeprom-config` signed-boot fields) if tamper-resistance of the
   *tool* itself matters to your deployment.
2. **Custom microcontroller subsystem** (if the CAN/LIN carrier in
   Section 14 uses its own MCU rather than being purely SPI/UART-
   peripheral to the Pi) — this is where a from-scratch bootloader
   design applies, and is the target of the flowchart below.

### 15.2 Flowchart (MCU subsystem bootloader)

```
                ┌───────────────────┐
                │   Power-on reset    │
                └──────────┬─────────┘
                           ▼
                ┌───────────────────┐
                │ Stage-0 (immutable,│  Lives in write-protected boot
                │ mask ROM / OTP)     │  sector — cannot itself be
                └──────────┬─────────┘  bricked by a bad app flash
                           ▼
                ┌───────────────────┐
                │ Check recovery-pin  │──── held low at boot? ───▶ Force recovery mode
                │ / recovery flag      │                              (Section 15.4)
                └──────────┬─────────┘
                           ▼ (normal path)
                ┌───────────────────┐
                │ Verify Stage-1       │──── signature invalid? ───▶ Force recovery mode
                │ signature (Ed25519   │
                │ or ECDSA, public key │
                │ burned into OTP)      │
                └──────────┬─────────┘
                           ▼ valid
                ┌───────────────────┐
                │ Check rollback       │──── version < min_version? ─▶ Reject, recovery mode
                │ counter (monotonic,  │
                │ fuse or protected     │
                │ flash sector)          │
                └──────────┬─────────┘
                           ▼ OK
                ┌───────────────────┐
                │ Jump to Stage-1       │
                │ (application image)   │
                └───────────────────┘
```

### 15.3 Firmware partitioning

```
┌─────────────────────────────────────────┐
│ Boot sector (immutable/OTP)  — Stage-0     │  never rewritten in the field
├─────────────────────────────────────────┤
│ Recovery partition (write-protected        │  minimal: just enough to
│ except via the recovery-mode path)         │  accept a new app image over
│                                              │  UART/USB-DFU
├─────────────────────────────────────────┤
│ Application partition A                     │  active app image
├─────────────────────────────────────────┤
│ Application partition B                     │  standby slot — new firmware
│                                              │  writes here, not over A,
│                                              │  until verified good
├─────────────────────────────────────────┤
│ Config / rollback-counter sector            │  monotonic counter, active-
│                                              │  slot pointer
└─────────────────────────────────────────┘
```

A/B partitioning means an interrupted or corrupt application update
never touches the currently-running image — Stage-0 always has a known-
good slot to fall back to.

### 15.4 Recovery mode

Entered when: a GPIO recovery pin/jumper is held during reset, Stage-1
signature check fails, or the rollback counter rejects the image.
Recovery mode exposes a minimal, well-tested protocol (UART bootloader
or USB DFU) that accepts a new signed application image regardless of
what state the application partitions are in — this is the actual
"anti-brick" property, and it only works if Stage-0 + the recovery
partition are kept small, simple, and essentially never touched after
initial factory programming.

### 15.5 Rollback protection

Monotonic counter in a protected flash sector or hardware fuse;
Stage-0 refuses to boot an application image whose embedded version
number is below the counter, and the counter only increments (never
decrements) on a verified successful boot of a newer image — this
prevents an attacker (or an accidental field mistake) from
reintroducing a known-vulnerable older firmware version.

---

## 16. Cloud architecture

### 16.1 System diagram

```
┌───────────────────┐        ┌───────────────────┐
│  Mini PC / Pi 5      │        │  Full PC workstation │
│  src/cloud/sync.py    │        │  rclone                │
│  (structured data)     │        │  (bulk binaries)        │
└──────────┬───────────┘        └──────────┬───────────┘
           │ REST + WebSocket                │ Drive API
           ▼                                  ▼
┌────────────────────────────────────────────────────┐
│  backend/app  (FastAPI)                                │
│   /oauth/token, /oauth/register   (auth.py)              │
│   routes_vehicles.py, routes_dtc.py, routes_sync.py       │
│   websocket_remote.py  (live session hub)                 │
│   db.py (SQLAlchemy) ──▶ Postgres/SQLite                   │
│   crypto.py  (Fernet, encrypted-at-rest technician notes)  │
└──────────────────────────┬───────────────────────────┘
                            │
                            ▼
                 ┌───────────────────┐
                 │ Google Drive          │  ← rclone remote, calibration +
                 │ (via rclone)           │    firmware + log archive
                 └───────────────────┘
```

### 16.2 API structure (existing `backend/app`)

| Endpoint group | File | Purpose |
|---|---|---|
| `/oauth/token`, `/oauth/register` | `auth.py`, `main.py` | OAuth2-password bearer tokens, technician accounts |
| Vehicle records | `routes_vehicles.py` | VIN profiles CRUD |
| DTC history | `routes_dtc.py` | DTC read/clear history |
| Sync | `routes_sync.py` | `PUT /sync/<table>/<record_id>` — the endpoint `CloudSyncClient.flush_queue()` targets, with `409` on conflict |
| Remote diagnostics | `websocket_remote.py` | Live session WebSocket hub for multi-device visibility |

### 16.3 Database schema

Mirrors `src/cloud/sync.py`'s `SCHEMA` (client-side cache) on the server
side via SQLAlchemy models in `backend/app/models.py`: `vin_profiles`,
`dtc_history`, `freeze_frames`, `live_snapshots`, `flash_history`,
`technician_notes` (encrypted via `crypto.py`), `log_files`. Add an
`ota_bundles` table (new) if implementing the OTA expansion from
Section 6: `(bundle_id, ecu, cal_id, signature, min_client_version,
published_at)`.

### 16.4 Security model

- OAuth2 bearer tokens (`auth.py::create_access_token`), role field
  (`technician`/`admin`) checked per-route.
- `technician_notes` encrypted at rest via Fernet
  (`crypto.py`) — the only column-level encryption in the current
  schema; extend the same pattern to any new sensitive field rather than
  introducing a second crypto approach.
- CORS currently `allow_origins=["*"]` in `main.py` for development —
  tighten to known desktop/Android/web origins before any production/
  multi-shop deployment, as the inline comment there already flags.
- OTA bundle integrity: sign bundles (Ed25519) at publish time, verify
  client-side before install — reuses the same signature-verification
  primitive as the bootloader's Stage-1 check ([Section 15](#15-bootloader-design))
  rather than a separate scheme.

### 16.5 rclone integration strategy

- Structured data (small, relational) goes through `backend/app`; bulk
  binary data (firmware dumps, full session logs) goes through rclone
  directly to Drive — don't try to push large binaries through the
  FastAPI backend, that's not what it's schema'd for.
- `rclone sync` (not `copy`) for the calibration archive so deletions
  propagate; a `--backup-dir` flag preserves anything sync would
  otherwise delete, giving you an undo path for accidental local
  deletions.
- Schedule via cron/Task Scheduler at an interval matched to how often
  new calibrations are authored (hourly is plenty; sub-hourly gains
  nothing for a single-shop deployment).

---

## 17. Manufacturing & supply chain

### 17.1 PCB fabrication workflow

1. Finalize schematic + layout (KiCad recommended — free, capable, and
   what most small-batch fabs' design-rule checkers are tuned against).
2. Run DRC/ERC, generate Gerbers + drill files + BOM/pick-and-place
   files.
3. Submit to a fab (JLCPCB, PCBWay for prototype/small-batch; a
   domestic fab if traceability/lead-time requirements demand it).
4. Prototype run (5–10 boards) → bring-up + test → revise if needed →
   production run.

### 17.2 Component sourcing

- Primary: DigiKey/Mouser for the transceivers/controllers (MCP2515,
  TJA1050, TJA1027) and passives — these are standard, multi-sourced
  parts with no single-vendor lock-in risk.
- Secondary/backup source for each critical part number, so a single
  distributor stockout doesn't halt a production run.
- Raspberry Pi 5 units: order through an authorized reseller (Pi
  Foundation partners) rather than gray-market channels, for warranty
  and supply consistency at volume.

### 17.3 Injection-molded enclosure production

Only justified past a few dozen units — below that, 3D-printed PETG
(Section 12) or a machined stock enclosure is cheaper per-unit than
mold tooling amortization. If volume justifies it: tooling quote from
the enclosure fab based on the CAD model from Section 12.2, expect
several weeks of tooling lead time before first-article parts.

### 17.4 Cable harness manufacturing

For volumes beyond hand-built pigtails: a harness house builds
OBD-II-to-terminal-block cables to a drawing (wire gauge, twisted-pair
spec for CAN-H/L, connector part numbers) rather than each unit being
individually hand-crimped — reduces per-unit labor and improves
consistency of the CAN pair's twist/length.

### 17.5 Quality assurance pipeline

1. Incoming inspection: spot-check transceiver/controller part
   markings against the BOM (counterfeit passives are a real risk on
   high-volume commodity parts sourced cheaply).
2. In-circuit test (ICT) or a simple bed-of-nails continuity fixture
   for assembled boards, if volume justifies fixture cost.
3. Functional test: every unit powers up, brings `can0` up, and
   round-trips a known CAN frame against a bench ECU simulator
   (`src/j2534/simulator.py` doubles as this bench simulator).
4. Burn-in: powered soak (a few hours) before shipping, to catch early-
   life component failures.

### 17.6 Packaging & logistics

Anti-static bag for the bare board/HAT, foam-lined box for the
assembled handheld unit (it's carrying an active-cooler fan and
terminal blocks that shouldn't take shipping shock directly on their
solder joints).

### 17.7 Vendor selection

Weight fab/distributor choice by: lead time, minimum order quantity,
willingness to provide a certificate of conformance for automotive-
adjacent parts, and — for the transceiver ICs specifically — genuine-
parts guarantees (this is a category with known counterfeit risk at the
cheapest sourcing tiers).

### 17.8 Cost optimization

- Panelize PCB orders (fab cost is dominated by panel area + setup, not
  per-board complexity, for small boards like this HAT).
- Standardize on parts already used elsewhere in the BOM (e.g. one TVS
  diode part number across CAN, LIN, and power-rail protection) to
  consolidate purchasing volume and reduce distinct line items.
- Buy Pi 5 units and NVMe drives at whatever cadence matches actual
  build rate — these are the BOM's most liquid/price-volatile parts, so
  avoid speculative bulk-buying them far ahead of assembly.

### 17.9 Timeline (indicative, prototype → small batch)

| Phase | Duration |
|---|---|
| Schematic + layout | 1–2 weeks |
| Prototype PCB fab + assembly | 1–2 weeks (with a quick-turn fab) |
| Bring-up + firmware bring-up | 1–2 weeks |
| Design revision (if needed) | 1 week |
| Small-batch fab + assembly (10–50 units) | 2–4 weeks |
| QA + packaging | 1 week |

---

## 18. Full technical architecture diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              HARDWARE LAYER                                │
│  Vehicle bus (CAN/LIN) ── Pi5 CAN/LIN HAT ── Mini PC USB-CAN/relay          │
│  ── Workstation (NVMe scratch + archive, optional GPU)                     │
├──────────────────────────────────────────────────────────────────────────┤
│                              FIRMWARE LAYER                                 │
│  Pi 5: Raspberry Pi OS Lite + SocketCAN + dtoverlay(mcp2515)                │
│  Carrier MCU (if used): Stage-0 (OTP) → Stage-1 verify → A/B app partitions │
├──────────────────────────────────────────────────────────────────────────┤
│                              TRANSPORT LAYER                                │
│  SocketCAN (can0) · ISO-TP (src/uds/client.py) · J2534 bridge              │
│  (Section 8) · USB-Ethernet (Pi↔Mini PC) · 2.5GbE (Mini PC↔Workstation)    │
├──────────────────────────────────────────────────────────────────────────┤
│                              SOFTWARE MODULE LAYER                          │
│  src/can · src/vin · src/pid · src/uds · src/ecu/trionic8                  │
│  src/sniffer · src/flashsafe · src/flashing · src/emulator                 │
│  src/calibration · src/plugins (gm, ford) · src/cloud · src/remote         │
│  src/j2534 (interface + simulator) · src/logging                           │
├──────────────────────────────────────────────────────────────────────────┤
│                              APPLICATION LAYER                             │
│  OEM tools (Tech2Win/TIS2000/GDS2/Techstream/ISTA/ODIS/FMP/HDS, licensed)  │
│  dashboard/index.html (GDS2-style web dashboard)                           │
│  android/ (transport reference)                                            │
├──────────────────────────────────────────────────────────────────────────┤
│                              CLOUD LAYER                                    │
│  backend/app (FastAPI: auth, vehicles, DTC, sync, remote WS)                │
│  rclone → Google Drive (calibration + firmware + log archive)              │
├──────────────────────────────────────────────────────────────────────────┤
│                              SECURITY LAYER                                 │
│  OAuth2 bearer tokens · Fernet-encrypted technician notes                   │
│  NullSeedKeyProvider fail-closed (docs/security-access-disclaimer.md)      │
│  Bootloader signature + rollback protection (Section 15)                   │
│  FlashSafeChecklist gating (Section 10)                                     │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 19. Embedded Linux optimization

Targeting Raspberry Pi OS Lite (Bookworm, 64-bit) for the Pi 5 capture
unit specifically — headless, CAN-bus-and-logging workload profile.

### 19.1 Kernel / boot tuning

`/boot/firmware/config.txt` additions beyond the CAN overlay in
Section 2:

```ini
# Disable unused peripherals to cut boot time and idle power
dtoverlay=disable-bt
dtoverlay=disable-wifi   # omit if Wi-Fi is your Pi↔MiniPC transport instead of USB-Eth
gpu_mem=16               # headless — no need for a larger GPU split
```

`/boot/firmware/cmdline.txt`: add `quiet` to reduce console log
volume during boot (faster boot, and console UART isn't your
diagnostic path anyway once LIN/UART is repurposed per Section 7.2).

### 19.2 Real-time scheduling for CAN capture

CAN frame timestamping accuracy benefits from taking the capture thread
off the default `SCHED_OTHER` scheduling class:

```bash
# Run the sniffer under a real-time priority (requires CAP_SYS_NICE
# or root, and a PREEMPT-capable kernel — Pi OS's default kernel has
# CONFIG_PREEMPT enabled)
chrt -f 50 python3 -m src.sniffer.engine --demo
```

For sustained low-jitter capture, consider the `raspberrypi-kernel`
in its `PREEMPT_RT`-patched variant if jitter in the low-microsecond
range matters for your capture use case — the stock `PREEMPT` kernel is
sufficient for UDS request/response and DTC/calibration-ID reads, which
aren't latency-critical at that scale.

### 19.3 CAN bus performance optimization

```bash
# Raise the socketcan queue length if bursts of frames are being dropped
sudo ip link set can0 txqueuelen 1000
# Confirm no bus-off/error-passive state during sustained capture
ip -details -statistics link show can0
```

Use `candump -t z can0` (SocketCAN's zero-based hardware timestamps)
rather than software timestamps in `src/sniffer/engine.py` when precise
inter-frame timing matters for LIN/CAN correlation analysis.

### 19.4 Logging efficiency

`src/logging/session.py`'s JSON+plaintext dual output is convenient but
not free on a Pi 5's SD/NVMe write bandwidth during a high-rate capture;
batch writes (buffer N entries, flush every few hundred ms) rather than
flushing per-frame, and prefer the NVMe HAT boot option from Section 2
over microSD for any deployment doing sustained logging — SD cards'
write-endurance and sustained-write-speed are both meaningfully worse
than even a budget NVMe SSD.

### 19.5 Memory footprint reduction

Raspberry Pi OS Lite already omits the desktop environment; further
trim with:

```bash
sudo apt purge -y triggerhappy raspi-config  # if not needed post-provisioning
sudo systemctl disable --now bluetooth hciuart
```

### 19.6 Boot time reduction

```bash
systemd-analyze blame   # identify the slowest units first, don't guess
sudo systemctl disable NetworkManager-wait-online.service  # common offender
```

Measure before and after each change (`systemd-analyze`) rather than
disabling services speculatively — a unit that looks slow in `blame`
output is sometimes blocking on something you actually need at boot
(e.g. the CAN interface itself, if brought up via a systemd unit rather
than at kernel/overlay level).

### 19.7 Security hardening

```bash
# Disable password SSH auth once key-based auth is confirmed working
sudo sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
# Keep the OS current
sudo apt update && sudo apt full-upgrade -y
# Firewall: only the ports this unit actually needs (SSH + the
# metadata-forwarding port to the Mini PC)
sudo apt install -y ufw
sudo ufw default deny incoming
sudo ufw allow from <mini-pc-ip> to any port 22
sudo ufw allow from <mini-pc-ip> to any port <forwarder-port>
sudo ufw enable
```

A field-deployed diagnostic unit is a small attack surface, but it's
one that talks to both a vehicle bus and a Windows PC — lock down SSH
and the network surface to just what the Mini PC pairing needs, same
principle as the CORS tightening called out in Section 16.4 for the
cloud backend.
