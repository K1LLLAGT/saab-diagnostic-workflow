# Build & run instructions

## Core Python engine (PID registry, VIN decoder, sniffer, flash-safe,
## flashing, emulator, plugins, calibration catalog, cloud sync client)

```bash
python3 -m pip install pytest
python3 -m pytest tests/ -q
```

Each module also runs standalone, e.g.:

```bash
python3 -m src.vin.decoder YS3FD45Y381234567
python3 -m src.sniffer.engine --demo
python3 -m src.flashsafe.checklist --demo
python3 -m src.flashing.engine --demo
python3 -m src.emulator.tech2 --demo
python3 -m src.plugins.loader --list
python3 -m src.calibration.catalog --ecu T8 --list
python3 -m src.cloud.sync --demo
python3 -m src.j2534.simulator --probe
```

## Cloud sync + remote diagnostics backend

```bash
python3 -m pip install -r backend/requirements.txt
# passlib 1.7.x cannot detect bcrypt>=4.1's version metadata; pin bcrypt
# as requirements.txt does (bcrypt==4.0.1) if you hit a
# "password cannot be longer than 72 bytes" error at import time.

python3 -m pytest backend/tests/ -q

# Run the server:
export SAABSUITE_JWT_SECRET="change-me-in-production"
export SAABSUITE_ENCRYPTION_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
uvicorn backend.app.main:app --reload --port 8000
```

Interactive API docs are then at `http://localhost:8000/docs`.

First-run account:

```bash
curl -X POST http://localhost:8000/oauth/register \
  -d "username=tech1&password=your-password-here"
```

## Web dashboard (GDS2-style UI)

Static HTML/CSS/JS — no build step required for local use:

```bash
python3 -m http.server -d dashboard 8080
# open http://localhost:8080
```

`dashboard/index.html` loads its logic from `dashboard/src/app.js`
(a plain, dependency-free ES script) via a `<script src="src/app.js">`
tag — the file above serves both directly, no bundler needed.

To host it as a Windows desktop app, wrap `dashboard/index.html` in
Electron (`electron dashboard/index.html`) or any Chromium-based webview
shell — no code changes required. Wire its demo functions (`sniffer`,
`flashsafe`, `flashing`, `emulator`, `cloud`, `remote` in
`dashboard/src/app.js`) to the real backend/CLI modules by replacing
their bodies with `fetch()` calls against `backend/app`'s REST/WebSocket
endpoints once you're running against a live vehicle instead of demo
data.

### Optional production bundle

A root-level `package.json` + `webpack.config.js` bundle
`dashboard/src/app.js` into a single minified `dashboard/dist/bundle.js`
— useful when packaging the dashboard into an Electron app or any
context where you want one production asset instead of the raw source
file. This is optional; it doesn't change how the dashboard runs locally.

```bash
npm ci
npm run build   # writes dashboard/dist/bundle.js
```

## Android transport layer

`android/` is a reference transport implementation, not a buildable app
module on its own — see `android/README.md` for what's included vs.
what a full app would still need (Activities, background service,
Room-backed offline cache, gauge UI). To build it as part of a real app:

1. Create a standard Android Studio project.
2. Copy `android/app/src/main/java/com/saabsuite/transport/*.kt` into
   your app module.
3. Merge `android/app/build.gradle.kts` dependencies and
   `AndroidManifest.xml` entries (USB host feature, USB device filter,
   INTERNET permission) into your project.
4. Implement the UI layer against `UsbOtgTransport` / `RemoteCanTransport`.

## Full test suite

```bash
python3 -m pip install pytest -r backend/requirements.txt
python3 -m pytest -q   # runs tests/ and backend/tests/ together (see pytest.ini)
```
