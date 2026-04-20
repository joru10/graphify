#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"

EXTRAS="${1:-core}"

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel

case "$EXTRAS" in
  core)
    "$VENV_DIR/bin/pip" install -e "$ROOT_DIR"
    ;;
  recommended)
    "$VENV_DIR/bin/pip" install -e "$ROOT_DIR[pdf,office,watch,svg,leiden]"
    ;;
  all)
    "$VENV_DIR/bin/pip" install -e "$ROOT_DIR[all]"
    ;;
  *)
    echo "Unknown extras profile: $EXTRAS"
    echo "Use one of: core | recommended | all"
    exit 1
    ;;
esac

echo

echo "Local setup complete."
echo "Use: $ROOT_DIR/scripts/run_graphify.sh --help"
