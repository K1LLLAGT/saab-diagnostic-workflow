#!/usr/bin/env bash
# ANDRAX 2.0 — environment loader.
# Usage:  source termux-backend/config/env.sh
#
# Safe to source from any directory and any shell profile. Idempotent.

# Load canonical paths (also sets ANDRAX_HOME).
_env_self="${BASH_SOURCE[0]:-$0}"
_env_dir="$(cd "$(dirname "$_env_self")" && pwd)"
# shellcheck source=./paths.sh
. "$_env_dir/paths.sh"

# Put the engine on PATH under the friendly name `andrax`.
if [ -d "$ANDRAX_ENGINE_DIR" ]; then
    case ":$PATH:" in
        *":$ANDRAX_ENGINE_DIR:"*) : ;;
        *) export PATH="$ANDRAX_ENGINE_DIR:$PATH" ;;
    esac
    # Provide `andrax` as an alias to engine.sh for interactive shells.
    if [ -n "${BASH_VERSION:-}${ZSH_VERSION:-}" ]; then
        alias andrax="$ANDRAX_ENGINE_DIR/engine.sh"
    fi
fi

# Go / Rust / pip user tool bins, if present.
for _bin in "$HOME/go/bin" "$HOME/.cargo/bin" "$HOME/.local/bin"; do
    if [ -d "$_bin" ]; then
        case ":$PATH:" in
            *":$_bin:"*) : ;;
            *) export PATH="$_bin:$PATH" ;;
        esac
    fi
done
unset _bin

# Default target-rate limiting knobs used by tool wrappers (be a good citizen).
export ANDRAX_HTTP_UA="${ANDRAX_HTTP_UA:-ANDRAX-2.0}"
export ANDRAX_DEFAULT_THREADS="${ANDRAX_DEFAULT_THREADS:-8}"

echo "[andrax] environment loaded. ANDRAX_HOME=$ANDRAX_HOME"
echo "[andrax] logs -> $ANDRAX_LOG_DIR   loot -> $ANDRAX_LOOT_DIR"
