#!/bin/bash
# Starts a throwaway Home Assistant for trying the card in a browser. Run it inside WSL.
# It listens on http://localhost:8123. Its settings folder is outside the repo.
# The first time, run tests/try/set_up.py once it has started.
# The very first start on a computer installs what Home Assistant needs, and Demo can fail to set
# up while that happens. If it does, stop it, delete the settings folder, and start it again.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
CONFIG="${TRY_CONFIG:-/root/mr-try}"
VENV="${TRY_VENV:-/root/mr/.venv}"

mkdir -p "$CONFIG/custom_components"
cp "$HERE/configuration.yaml" "$CONFIG/configuration.yaml"
ln -sfn "$REPO/custom_components/morning_routine" "$CONFIG/custom_components/morning_routine"
exec "$VENV/bin/hass" -c "$CONFIG"
