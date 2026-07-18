# ANDRAX 2.0

A user-space, ANDRAX-style penetration-testing workbench for modern Android
(e.g. Samsung tablets) built entirely on **Termux** + **proot-distro**.

ANDRAX 2.0 is a reimagining of the original ANDRAX concept for devices where
kernel-level tricks (chroot from init, loop mounts, raw packet injection,
SELinux bypass) are **not available**. Instead of fighting the modern Android
security model, ANDRAX 2.0 lives entirely in user space:

* **Termux** provides the base runtime (packages, Python, Go, Rust, git).
* **proot-distro** provides an optional Kali/Debian/Arch userland for tools that
  are not packaged for Termux.
* A **launcher system**, **workflow engine**, and **scripting engine** glue the
  tools together and expose them to both the CLI and a companion Android app.

> ⚠️ **Authorized use only.** ANDRAX 2.0 bundles standard, publicly available
> security tools (nmap, sqlmap, hydra, nikto, the Metasploit Framework, etc.).
> Use it **only** against systems you own or are explicitly authorized to test.
> You are responsible for complying with all applicable laws. See `LICENSE.md`.

## Layers

1. **Android app (`android-app/`)** — an ANDRAX-style category/tool browser that
   launches Termux scripts. It performs **no** privileged operations; it is a
   thin front-end that dispatches to the Termux backend.
2. **Termux backend (`termux-backend/`)** — install scripts, environment config,
   and one launcher script per tool. Every tool script validates its
   environment, prints usage when called with no args, logs to a central
   directory, and returns proper exit codes.
3. **Launcher + workflow + scripting engines** — `launcher-system/`,
   `workflow-engine/`, and `scripting-engine/` provide the ANDRAX-style
   registry, category dispatch, chained workflows, and a single entrypoint.

## Quick start

```sh
# 1. In Termux
tar -xzf ANDRAX-2.0.tar.gz
cd ANDRAX-2.0

# 2. Install the backend
bash termux-backend/setup/install_termux_packages.sh
bash termux-backend/setup/install_python_tools.sh
# (optional) bash termux-backend/setup/setup_proot_kali.sh

# 3. Load the environment
source termux-backend/config/env.sh

# 4. Use the scripting engine
./scripting-engine/engine.sh list-tools
./scripting-engine/engine.sh list-workflows
./scripting-engine/engine.sh run-tool nmap -- -sV scanme.nmap.org
./scripting-engine/engine.sh run-workflow recon_basic -- example.com
```

See `INSTALL.md` for full setup and app-build instructions.

## Repository layout

```
ANDRAX-2.0/
├── README.md            # this file
├── INSTALL.md           # full install + build guide
├── LICENSE.md           # license + legal/authorized-use notice
├── android-app/         # ANDRAX-style front-end (Kotlin skeleton)
├── termux-backend/      # install scripts, env config, per-tool launchers
├── launcher-system/     # tool_registry.json + launch/dispatch scripts
├── workflow-engine/     # chained workflows + shared shell libs
└── scripting-engine/    # single entrypoint (engine.sh) + helper scripts
```
