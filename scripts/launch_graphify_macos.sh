#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNNER="$ROOT_DIR/scripts/run_graphify.sh"

if [[ ! -x "$RUNNER" ]]; then
  osascript -e 'display dialog "Missing runner script at scripts/run_graphify.sh" buttons {"OK"} default button "OK" with icon stop'
  exit 1
fi

TARGET_DIR="$(osascript <<'APPLESCRIPT'
set chosenFolder to choose folder with prompt "Choose the folder to graphify"
POSIX path of chosenFolder
APPLESCRIPT
)"

MODE="$(osascript <<'APPLESCRIPT'
choose from list {"Full scan", "Update existing graph", "Watch mode"} with prompt "Select Graphify mode" default items {"Full scan"}
APPLESCRIPT
)"

if [[ "$MODE" == "false" ]]; then
  exit 0
fi

GRAPHIFY_ARGS=""
case "$MODE" in
  *"Full scan"*)
    GRAPHIFY_ARGS="\"$TARGET_DIR\""
    ;;
  *"Update existing graph"*)
    GRAPHIFY_ARGS="\"$TARGET_DIR\" --update"
    ;;
  *"Watch mode"*)
    GRAPHIFY_ARGS="\"$TARGET_DIR\" --watch"
    ;;
esac

EXTRA_ARGS="$(osascript <<'APPLESCRIPT'
text returned of (display dialog "Optional extra args (leave blank if none)" default answer "" buttons {"Cancel", "Run"} default button "Run")
APPLESCRIPT
)"

osascript <<APPLESCRIPT
tell application "Terminal"
  activate
  do script "cd \"$ROOT_DIR\"; \"$RUNNER\" $GRAPHIFY_ARGS $EXTRA_ARGS; echo; echo 'Press any key to close...'; read -n 1"
end tell
APPLESCRIPT
