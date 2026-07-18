#!/usr/bin/env bash
# ANDRAX 2.0 — canonical path definitions.
# Sourced by env.sh, the engine, and every tool script. Never run directly.

# Resolve ANDRAX_HOME to the repository root, no matter where we are sourced
# from, unless the caller already set it.
if [ -z "${ANDRAX_HOME:-}" ]; then
    _paths_self="${BASH_SOURCE[0]:-$0}"
    _paths_dir="$(cd "$(dirname "$_paths_self")" && pwd)"
    # config/ -> termux-backend/ -> ANDRAX-2.0/
    ANDRAX_HOME="$(cd "$_paths_dir/../.." && pwd)"
fi
export ANDRAX_HOME

# Component roots
export ANDRAX_BACKEND="$ANDRAX_HOME/termux-backend"
export ANDRAX_TOOLS_DIR="$ANDRAX_BACKEND/tools"
export ANDRAX_LAUNCHER_DIR="$ANDRAX_HOME/launcher-system"
export ANDRAX_WORKFLOW_DIR="$ANDRAX_HOME/workflow-engine"
export ANDRAX_ENGINE_DIR="$ANDRAX_HOME/scripting-engine"
export ANDRAX_REGISTRY="$ANDRAX_LAUNCHER_DIR/tool_registry.json"

# Per-user state (logs + captured output). Overridable via ANDRAX_STATE.
export ANDRAX_STATE="${ANDRAX_STATE:-$HOME/.andrax}"
export ANDRAX_LOG_DIR="$ANDRAX_STATE/logs"
export ANDRAX_LOOT_DIR="$ANDRAX_STATE/loot"
export ANDRAX_RUN_DIR="$ANDRAX_STATE/run"

# proot userland used for tools not packaged in Termux.
export ANDRAX_PROOT_DISTRO="${ANDRAX_PROOT_DISTRO:-kali}"

mkdir -p "$ANDRAX_LOG_DIR" "$ANDRAX_LOOT_DIR" "$ANDRAX_RUN_DIR" 2>/dev/null || true
