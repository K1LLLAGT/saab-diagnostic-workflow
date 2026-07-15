# OEM plugin API

Every OEM plugin lives at `plugins/<oem>/` and consists of:

```
plugins/<oem>/manifest.json
plugins/<oem>/plugin.py
plugins/<oem>/pids_<oem>_extended.json   (referenced by manifest "pidfiles")
```

## manifest.json

```json
{
  "oem": "gm",
  "protocols": ["ISO15765", "GMLAN", "KWP2000"],
  "pidfiles": ["pids_gm_extended.json"],
  "flashhandler": "plugin.py:Plugin.execute_flash",
  "calibrationcatalog": "calibrations/",
  "extendedservices": ["haldex_relearn", "epb_service_mode"],
  "minyear": 1996,
  "maxyear": 2026
}
```

All eight fields are required — `src/plugins/loader.py::PluginManifest`
rejects a manifest missing any of them at discovery time rather than
failing later with a confusing error.

## plugin.py

Must define a class `Plugin(OEMPlugin)` (see `src/plugins/base.py` for
the full abstract contract). Required methods:

| Method | Purpose |
|---|---|
| `initialize(vehicle_info)` | Bind the plugin instance to one vehicle/ECU set |
| `get_extended_pids()` | Return this OEM's extended PID/DID definitions |
| `decode_response(pid, data)` | Decode a raw response for an extended PID |
| `run_routine(routine_id, params)` | Execute an actuator test / OEM routine |

Optional (raise `NotImplementedError` if unsupported, as
`plugins/ford/plugin.py` does for flashing):

| Method | Purpose |
|---|---|
| `prepare_flash(cal_file)` | Validate a calibration against the catalog before flashing |
| `execute_flash(blocks)` | Delegate to `src.flashing.engine.FlashSession` |
| `recover_flash()` | Enter recovery-mode reflash |
| `lookup_calibrations(vin)` | VIN → applicable calibrations |
| `blocking_dtc_codes()` | Extra DTC prefixes that should block flashing |

## Loading a plugin

```python
from src.plugins.loader import PluginRegistry

registry = PluginRegistry("plugins")
registry.discover()
plugin = registry.instantiate("gm")
plugin.initialize(vehicle_info)
```

## Security access

`OEMPlugin.seed_key_provider` defaults to `NullSeedKeyProvider`, which
fails closed. See `docs/security-access-disclaimer.md` before wiring in
a real one.

## Writing a new plugin

1. Copy `plugins/ford/` as a starting template (the more conservative
   of the two reference plugins — it stubs flashing entirely).
2. Fill in `manifest.json` with your OEM's protocol set and year range.
3. Implement PID decoding against your OEM's DID map.
4. Add calibration records under `calibrations/<ECU>/` (see
   `docs/ecosystem-architecture.md` → "Calibration catalog").
5. Run `python3 -m src.plugins.loader --list` to confirm discovery, and
   add a test mirroring `tests/test_plugin_loader.py`.
