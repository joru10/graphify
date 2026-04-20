#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG_DIR="$ROOT_DIR/macos/GraphifyDesktop"
BUILD_DIR="$PKG_DIR/.build/release"
BIN_PATH="$BUILD_DIR/GraphifyDesktop"
APP_DIR="$ROOT_DIR/macos/Graphify Desktop.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"

if [[ ! -f "$PKG_DIR/Package.swift" ]]; then
  echo "Missing Swift package at $PKG_DIR"
  exit 1
fi

swift build -c release --package-path "$PKG_DIR"

rm -rf "$APP_DIR"
mkdir -p "$MACOS_DIR"
cp "$BIN_PATH" "$MACOS_DIR/GraphifyDesktop"
chmod +x "$MACOS_DIR/GraphifyDesktop"

cat > "$CONTENTS_DIR/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>CFBundleName</key>
    <string>Graphify Desktop</string>
    <key>CFBundleDisplayName</key>
    <string>Graphify Desktop</string>
    <key>CFBundleIdentifier</key>
    <string>com.graphify.desktop</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleExecutable</key>
    <string>GraphifyDesktop</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>GraphifyRepoRoot</key>
    <string>$ROOT_DIR</string>
  </dict>
</plist>
EOF

echo "Created: $APP_DIR"
echo "You can pin this app in Dock or move it to /Applications."
