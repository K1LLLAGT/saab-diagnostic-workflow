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
