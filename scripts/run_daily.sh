#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
CONFIG_PATH="${1:-$HOME/.sms-followup/config.json}"
PYTHON_BIN="${PYTHON:-/usr/bin/python3}"
if [ "$#" -gt 0 ]; then
  shift
fi

cd "$PROJECT_DIR"
exec "$PYTHON_BIN" -m sms_followup --config "$CONFIG_PATH" "$@"
