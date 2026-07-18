#!/usr/bin/env bash
# ANDRAX 2.0 — workflow prompt/confirmation library.
# Source: . "$ANDRAX_WORKFLOW_DIR/libs/prompts.sh"

# ask "Question?" default_value  -> echoes the answer
ask() {
    local q="$1" def="${2:-}" ans
    if [ -n "$def" ]; then read -r -p "$q [$def]: " ans; echo "${ans:-$def}"
    else read -r -p "$q: " ans; echo "$ans"; fi
}

# confirm "Proceed?"  -> returns 0 on yes. Honours ANDRAX_ASSUME_YES=1 (non-interactive).
confirm() {
    local q="${1:-Proceed?}" ans
    if [ "${ANDRAX_ASSUME_YES:-0}" = "1" ]; then return 0; fi
    read -r -p "$q [y/N]: " ans
    case "$ans" in y|Y|yes|YES) return 0;; *) return 1;; esac
}

# require_scope <target> — records/acknowledges authorization for a target.
require_scope() {
    local target="$1" flag="${ANDRAX_STATE:-$HOME/.andrax}/.authorized"
    mkdir -p "$(dirname "$flag")"
    if [ -f "$flag" ]; then return 0; fi
    echo "-------------------------------------------------------------"
    echo " AUTHORIZED TESTING ONLY"
    echo " Target: $target"
    echo " Confirm you own or are explicitly authorized to test this target."
    echo "-------------------------------------------------------------"
    if confirm "I have authorization to test $target"; then
        date -Is > "$flag"
        return 0
    fi
    echo "Authorization not confirmed. Aborting."
    return 1
}
