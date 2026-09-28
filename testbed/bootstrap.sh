#!/usr/bin/env bash
# ==============================================================================
# LabSense testbed — install host-side dependencies (idempotent).
#
#   backend/.venv          FastAPI backend + the E2E test tooling (pytest,
#                          httpx, websockets are already in requirements.txt)
#   frontend/node_modules  React/Vite dashboard
#
# Safe to run repeatedly: pip and npm skip anything already satisfied. Used by
# `testbed.sh up` and when a new cloud environment is set up.
# ==============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"

log() { printf '\033[0;36m[bootstrap]\033[0m %s\n' "$*"; }

# --- Backend -------------------------------------------------------------------
if [ ! -x "$ROOT/backend/.venv/bin/python" ]; then
    log "Creating backend/.venv"
    "$PYTHON" -m venv "$ROOT/backend/.venv"
fi
log "Installing backend requirements"
"$ROOT/backend/.venv/bin/python" -m pip install --quiet --disable-pip-version-check \
    -r "$ROOT/backend/requirements.txt"

# --- Frontend ------------------------------------------------------------------
# `npm install` rather than `npm ci`: it reuses an existing node_modules, so a
# cached container only pays for what changed.
log "Installing frontend packages"
(cd "$ROOT/frontend" && npm install --no-audit --no-fund --loglevel=error)

log "Dependencies ready"
