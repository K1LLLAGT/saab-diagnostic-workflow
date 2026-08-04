# SAAB-SUITE — Android companion (transport layer)

This directory contains the Android transport-layer reference
implementation described in `docs/ecosystem-architecture.md`: USB-OTG
passthrough to a J2534-class adapter, and a Remote CAN gateway client
(TCP/UDP/WebSocket) for when a phone is paired with a desktop/backend
instance instead of a direct USB adapter.

This is **not** a full Android application (Activities, ViewModels, the
touch-optimized gauge UI, background logging service, etc.) — building
that out is a substantial follow-on project of its own. What's here is:

- `RemoteCanProtocol.md` — the wire protocol Remote CAN speaks, matching
  `src/remote/client.py`'s `RemoteMessage` contract on the backend side.
- `app/src/main/java/com/saabsuite/transport/UsbOtgTransport.kt` — a
  working USB-OTG device-discovery + bulk-transfer wrapper using
  `android.hardware.usb`, structured around the same
  open/connect/read/write/disconnect/close lifecycle as
  `src/j2534/simulator.py`.
- `app/src/main/java/com/saabsuite/transport/RemoteCanTransport.kt` — a
  WebSocket client implementing the Remote CAN protocol.
- `app/build.gradle.kts`, `settings.gradle.kts`, `AndroidManifest.xml` —
  minimal scaffold sufficient to drop these transports into a real app
  module.
- `app/src/main/java/com/saabsuite/MainActivity.kt` — an empty
  placeholder activity that satisfies the manifest's launcher-activity
  reference so the module actually builds; replace it with real UI
  (Activities/ViewModels/gauge screens) when building this out further.

## Design notes carried over from the desktop suite

- **Auto-reconnect**: `RemoteCanTransport` retries with exponential
  backoff (see `connectWithRetry`), matching the desktop's tolerance for
  a flaky USB connection.
- **Offline VIN cache / background logging / low-power mode**: these are
  application-level concerns (Room database, a foreground Service,
  `JobScheduler`/`WorkManager` batching) that sit on top of these
  transports, not part of the transport layer itself. They're described
  in `docs/ecosystem-architecture.md` but not implemented here — wire
  them up using `src.cloud.sync.OfflineCache`'s SQLite schema as the
  reference for what an on-device cache needs to hold.
- **Haptic alerts / GPU-accelerated graphs**: standard Android APIs
  (`Vibrator` / `VibrationEffect`, Jetpack Compose Canvas or a charting
  library) — no protocol-level work needed, so left to the app layer.
