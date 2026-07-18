# ANDRAX 2.0 — Installation & Build Guide

This guide covers a **non-rooted** modern Android device (Samsung tablet or
phone) running Termux. Root is **not** required; a few tools simply have reduced
capability without it (noted below).

---

## 0. Prerequisites

* Android 9+ (tested pattern: Samsung One UI, Android 12–14).
* **Termux** from F-Droid or GitHub — **not** the Play Store build, which is
  outdated and cannot install current packages.
* **Termux:API** app (optional, from F-Droid) for battery/clipboard/notification
  bridges and for the app↔backend intent bridge.
* ~4–6 GB free storage if you install the optional proot Kali userland.

```sh
# In Termux, first run:
termux-setup-storage
pkg update -y && pkg upgrade -y
```

---

## 1. Extract the archive

```sh
cd ~
tar -xzf ANDRAX-2.0.tar.gz
cd ANDRAX-2.0
```

Make everything executable (the archive should already carry the bits, but this
is idempotent):

```sh
find . -name '*.sh' -exec chmod +x {} \;
chmod +x scripting-engine/engine.sh launcher-system/*.sh
```

---

## 2. Install the Termux backend

Run the setup scripts in order. Each is idempotent and safe to re-run.

```sh
bash termux-backend/setup/install_termux_packages.sh   # base pkgs + core tools
bash termux-backend/setup/install_python_tools.sh      # pip-based tools
bash termux-backend/setup/install_go_tools.sh          # go-based tools (optional)
bash termux-backend/setup/install_rust_tools.sh        # rust-based tools (optional)
```

Optional Kali userland (for tools not packaged in Termux, e.g. wpscan, some
Metasploit modules):

```sh
bash termux-backend/setup/setup_proot_kali.sh
```

---

## 3. Load the environment

```sh
source termux-backend/config/env.sh
```

Add it to your shell profile so it loads automatically:

```sh
echo "source ~/ANDRAX-2.0/termux-backend/config/env.sh" >> ~/.bashrc
```

This exports `ANDRAX_HOME`, `ANDRAX_LOG_DIR`, `ANDRAX_LOOT_DIR`, and puts the
engine on your `PATH` as `andrax`.

---

## 4. Verify

```sh
andrax doctor            # environment self-check
andrax list-tools
andrax list-workflows
andrax run-tool nmap -- -sV scanme.nmap.org
```

Logs land in `~/.andrax/logs/`, captured output/loot in `~/.andrax/loot/`.

---

## 5. Build / install the Android app prototype

The app under `android-app/` is a **Kotlin skeleton** intended to be opened in
Android Studio (Giraffe+). It is a front-end only; it dispatches to the Termux
backend via the `RUN_COMMAND` intent (Termux) or a `am`/URL bridge.

1. Open Android Studio → **Open** → select `android-app/`.
2. Let Gradle sync (the skeleton targets `compileSdk 34`, `minSdk 26`).
3. The tool catalog is read from `src/main/assets/tool_registry.json` — this is a
   copy of `launcher-system/tool_registry.json`. Keep them in sync (see below).
4. Build & install onto the device that also runs Termux.

### App ↔ Termux bridge

The app uses Termux's `RUN_COMMAND` intent. For it to work you must, once:

```sh
# In Termux
mkdir -p ~/.termux
echo "allow-external-apps=true" >> ~/.termux/termux.properties
termux-reload-settings
```

and grant the app the `com.termux.permission.RUN_COMMAND` permission (declared in
`AndroidManifest.xml`). The app then launches, e.g.:

```
RUN_COMMAND_PATH = /data/data/com.termux/files/home/ANDRAX-2.0/scripting-engine/engine.sh
RUN_COMMAND_ARGUMENTS = run-tool,nmap,--,-sV,<target>
```

### Keeping the app catalog in sync

```sh
cp launcher-system/tool_registry.json \
   android-app/src/main/assets/tool_registry.json
```

---

## 6. Uninstall / clean

```sh
rm -rf ~/.andrax          # logs + loot
rm -rf ~/ANDRAX-2.0       # the toolkit
proot-distro remove kali  # if you installed the userland
```

---

## Notes on capabilities without root

| Capability                         | Non-root behavior                              |
|------------------------------------|------------------------------------------------|
| TCP/UDP scanning (nmap)            | ✅ works (connect scans)                        |
| SYN / raw-socket scans             | ❌ needs root; scripts fall back to `-sT`       |
| Wi-Fi monitor mode / injection     | ❌ not possible on stock Android                |
| Wi-Fi scan / info                  | ✅ via `termux-wifi-scaninfo` (Termux:API)      |
| MITM proxy (mitmproxy)             | ✅ as an HTTP(S) proxy the user configures      |
| ARP spoofing / ettercap            | ❌ needs raw sockets; use app-layer MITM instead|
| Metasploit Framework               | ✅ runs; some modules need the proot userland   |
