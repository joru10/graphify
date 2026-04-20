#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_BIN="$ROOT_DIR/.venv/bin"

if [[ ! -x "$VENV_BIN/graphify" ]]; then
  echo "graphify not installed in .venv yet."
  echo "Run: $ROOT_DIR/scripts/setup_local.sh recommended"
  exit 1
fi

exec "$VENV_BIN/graphify" "$@"
