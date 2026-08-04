# SAAB Diagnostic Workflow Suite

![Status](https://img.shields.io/badge/status-active-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)
![Platform](https://img.shields.io/badge/platform-Win7--SAAB%20VM-lightgrey)
![Interface](https://img.shields.io/badge/interface-Mongoose%20Pro%20GM%20II-orange)

A complete, technician-grade diagnostic workflow for SAAB vehicles using:

- Mongoose Pro GM II (J2534)
- Win7-SAAB VM (VMware Workstation Pro)
- GlobalTIS SPS
- GDS2
- TIS2000
- SAAB-SUITE automation scripts

---

## Quick start

```bash
./saab workflow      # Full guided diagnostic workflow
./saab quick-scan    # Fast CAN + DTC scan
./saab doctor        # Environment self-test
```

---

## Documentation

- [Diagnostic Workflow](docs/saab-diagnostic-workflow.md)
- [9-3 Aero XWD Workflow](docs/workflows/saab-9-3-aero-xwd.md)
- [Module Programming Matrix](docs/module-programming-matrix.md)
- [Architecture](docs/architecture.md)
- [Ecosystem Architecture](docs/ecosystem-architecture.md) — broader tooling layer below
- [Hybrid Hardware Blueprint](docs/hybrid-hardware-blueprint.md) — Pi 5 + Mini PC (N100) + ROG Strix workstation hardware build, wiring, PCB, BOM, and manufacturing
- [Plugin API](docs/plugin-api.md)
- [Security-Access Disclaimer](docs/security-access-disclaimer.md) — read before touching flashing
- [Build Instructions](docs/build-instructions.md)

---

## Ecosystem layer

Alongside the original single-vehicle Trionic T8 workflow, this repo
also includes a broader technician-tooling scaffold: a PID registry, VIN
decoder, CAN sniffer engine, flash-safe checklist, an ECU flashing
protocol state machine, a Tech2/MDI-style emulator core, an OEM plugin
architecture (`plugins/gm`, `plugins/ford`), an SPS-style calibration
catalog, a FastAPI cloud-sync + remote-diagnostics backend, a GDS2-style
web dashboard, and an Android transport-layer reference (USB-OTG +
Remote CAN). All of it is genuinely implemented and tested (`tests/`,
`backend/tests/`) — see
[docs/ecosystem-architecture.md](docs/ecosystem-architecture.md) for
what's a full implementation versus an architecture/protocol scaffold
(notably: no real OEM security-access algorithm is included — see the
disclaimer above — and Android/Windows packaging is a transport/UI
reference rather than a shippable app).

```bash
python3 -m pytest -q          # 45 tests: core engine + cloud backend
python3 -m http.server -d dashboard 8080   # GDS2-style dashboard at :8080
uvicorn backend.app.main:app --reload      # cloud sync + remote diagnostics API
```

---

## Logging

All diagnostic runs are logged under:

```
logs/diag-YYYYMMDD-HHMM/
```

Each run captures:

- Command line used
- Basic environment snapshot
- Tool output

---

## Philosophy

Deterministic, reproducible, technician-friendly.
Clone → Follow docs → Run `./saab workflow` → Get consistent results.
