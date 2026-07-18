#!/usr/bin/env bash
# ANDRAX 2.0 — install Go-based security tools (ProjectDiscovery et al.).
# Optional. Requires the 'golang' package (installed by install_termux_packages.sh).
set -euo pipefail

command -v go >/dev/null 2>&1 || { echo "[andrax-setup] go not found; run install_termux_packages.sh first"; exit 1; }

export GOBIN="$HOME/go/bin"
mkdir -p "$GOBIN"

# module@version -> installed binary in $GOBIN
GO_TOOLS=(
    github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest   # subdomains
    github.com/projectdiscovery/httpx/cmd/httpx@latest              # http probing
    github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest         # template scanner
    github.com/projectdiscovery/naabu/v2/cmd/naabu@latest           # fast port scan
    github.com/ffuf/ffuf/v2@latest                                  # web fuzzing
    github.com/OJ/gobuster/v3@latest                                # dir/dns brute
)

for mod in "${GO_TOOLS[@]}"; do
    echo "  -> go install $mod"
    go install "$mod" || echo "     [warn] failed to build '$mod'; skipping"
done

echo "[andrax-setup] Go tools installed to $GOBIN (on PATH via env.sh)."
echo "[andrax-setup] Tip: run 'nuclei -update-templates' to fetch detection templates."
