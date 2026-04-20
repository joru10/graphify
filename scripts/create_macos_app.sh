#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/macos/Graphify Launcher.app"
LAUNCHER="$ROOT_DIR/scripts/launch_graphify_macos.sh"

if [[ ! -x "$LAUNCHER" ]]; then
  echo "Missing launcher script: $LAUNCHER"
  exit 1
fi

TMP_SCRIPT="$(mktemp)"
cat > "$TMP_SCRIPT" <<APPLESCRIPT
set launcher to POSIX file "$LAUNCHER" as text
tell application "Terminal"
  activate
  do script quoted form of POSIX path of launcher
end tell
APPLESCRIPT

rm -rf "$APP_DIR"
osacompile -o "$APP_DIR" "$TMP_SCRIPT"
rm -f "$TMP_SCRIPT"

echo "Created: $APP_DIR"
echo "You can pin this app in Dock or move it to /Applications."
