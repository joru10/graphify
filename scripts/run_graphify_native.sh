#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$ROOT_DIR/.venv/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
  "$ROOT_DIR/scripts/setup_local.sh" recommended
fi

TARGET_DIR="${1:-}"
MODE="${2:-full}"

if [[ -z "$TARGET_DIR" ]]; then
  echo "Usage: $0 <target_dir> [full|update]" >&2
  exit 1
fi

exec "$VENV_PY" "$ROOT_DIR/scripts/run_graphify_native.py" "$TARGET_DIR" --mode "$MODE"
