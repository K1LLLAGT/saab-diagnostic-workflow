#!/usr/bin/env bash
# ANDRAX 2.0 — install Python-based security tools via pip.
# Idempotent.
set -euo pipefail

echo "[andrax-setup] Upgrading pip..."
python -m pip install --upgrade pip wheel setuptools

# pip packages that build cleanly on Termux/Android (aarch64).
PIP_TOOLS=(
    dnsenum-like:dnspython        # DNS toolkit used by our dnsenum.sh wrapper
    mitmproxy                     # app-layer MITM / intercepting proxy
    wafw00f                       # WAF fingerprinting
    dirsearch                     # web path brute-forcing (pure python)
    sublist3r                     # subdomain enumeration
    theHarvester                  # OSINT email/host gathering
    arjun                         # HTTP parameter discovery
    droopescan                    # CMS scanner (drupal/wordpress/etc)
)

install_pip() {
    local spec="$1" name pkg
    # entries may be "label:pkg" or just "pkg"
    if [[ "$spec" == *:* ]]; then pkg="${spec#*:}"; else pkg="$spec"; fi
    echo "  -> pip install $pkg"
    python -m pip install --upgrade "$pkg" \
        || echo "     [warn] failed to install '$pkg'; skipping"
}

for t in "${PIP_TOOLS[@]}"; do install_pip "$t"; done

echo "[andrax-setup] Python tools installed to $(python -m site --user-base)/bin (on PATH via env.sh)."
