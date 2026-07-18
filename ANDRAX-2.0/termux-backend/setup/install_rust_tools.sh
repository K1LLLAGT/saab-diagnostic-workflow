#!/usr/bin/env bash
# ANDRAX 2.0 — install Rust-based security tools via cargo.
# Optional. Requires the 'rust' package (installed by install_termux_packages.sh).
set -euo pipefail

command -v cargo >/dev/null 2>&1 || { echo "[andrax-setup] cargo not found; run install_termux_packages.sh first"; exit 1; }

# crate -> installed binary in ~/.cargo/bin
CARGO_TOOLS=(
    rustscan        # fast port scanner (feeds nmap)
    feroxbuster     # recursive content discovery
)

for crate in "${CARGO_TOOLS[@]}"; do
    echo "  -> cargo install $crate"
    cargo install "$crate" || echo "     [warn] failed to build '$crate'; skipping"
done

echo "[andrax-setup] Rust tools installed to ~/.cargo/bin (on PATH via env.sh)."
