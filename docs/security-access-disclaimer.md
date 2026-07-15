# Security-access & flashing disclaimer

This suite implements the **protocol mechanics** of ECU security access
and reprogramming — session control, seed/key message framing,
block-transfer with flow control, resume-safe checkpointing, recovery
mode — across `src/flashing/engine.py`, `src/uds/client.py`, and
`src/plugins/base.py`.

It does **not** ship, compute, or reverse-engineer any real
manufacturer security-access (seed→key) algorithm.

- `SeedKeyProvider` (`src/plugins/base.py`) is the extension point a
  licensed algorithm plugs into.
- The default, `NullSeedKeyProvider`, fails closed: calling
  `compute_key()` always raises `NotImplementedError`. `FlashSession`
  checks for this explicitly and refuses to proceed
  (`src/flashing/engine.py::FlashSession._security_access`), rather than
  silently sending a wrong or trivial key.
- `plugins/gm/plugin.py` and `plugins/ford/plugin.py` demonstrate the
  contract but do not supply real keys either — `Plugin.seed_key_provider`
  defaults to `NullSeedKeyProvider` until you set one.

## Why this boundary exists

Manufacturer security-access algorithms gate write access to
safety-critical (ABS, airbag, steering) and emissions-relevant (ECU
calibration) modules. They are normally licensed by the OEM to tool
vendors under contract (this is how Mongoose, Tech2, Autel, etc.
legitimately unlock programming access) rather than published. This
repository has no such license, so it does not include one.

If you have a legitimate need for real security access — you are a
licensed tool vendor, an OEM-authorized shop with a Techline
Connect/GlobalTIS/SPS subscription, or otherwise hold the rights to the
algorithm for your specific ECU — supply it yourself via a
`SeedKeyProvider` implementation in your own OEM plugin. Do not ask an
AI assistant to derive or reverse-engineer one from captured seed/key
pairs; that is both unlikely to work reliably (most modern algorithms
use manufacturer secret keys/HSMs) and outside what this project
supports.

## Legal context worth knowing before extending this further

- Reflashing emissions-relevant calibrations on a vehicle in a way that
  defeats or worsens emissions controls can violate the Clean Air Act
  (US) / equivalent regulations elsewhere (EPA "defeat device" rules).
- Circumventing anti-theft/immobilizer security access without
  authorization may implicate computer-fraud or anti-theft statutes
  depending on jurisdiction.
- The flash-safe checklist (`src/flashsafe/checklist.py`) exists to
  reduce the risk of bricking a module during a *legitimate* flash — it
  is not a substitute for having the right to perform that flash in the
  first place.
