#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/macos/Graphify Launcher.app"
APPLESCRIPT_SRC="$ROOT_DIR/macos/GraphifyLauncher.applescript"

if [[ ! -f "$APPLESCRIPT_SRC" ]]; then
  echo "Missing AppleScript source: $APPLESCRIPT_SRC"
  exit 1
fi

TMP_SCRIPT="$(mktemp)"
ROOT_ESCAPED="$(printf '%s' "$ROOT_DIR" | sed 's/[&/]/\\&/g')"
sed "s/__ROOT_DIR__/$ROOT_ESCAPED/g" "$APPLESCRIPT_SRC" > "$TMP_SCRIPT"

rm -rf "$APP_DIR"
osacompile -o "$APP_DIR" "$TMP_SCRIPT"
rm -f "$TMP_SCRIPT"

echo "Created: $APP_DIR"
echo "You can pin this app in Dock or move it to /Applications."
