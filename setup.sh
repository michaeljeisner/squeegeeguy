#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST="$SCRIPT_DIR/com.squeegeeguy.leadgen.plist"
AGENTS_DIR="$HOME/Library/LaunchAgents"

mkdir -p "$AGENTS_DIR"
ln -sf "$PLIST" "$AGENTS_DIR/com.squeegeeguy.leadgen.plist"
launchctl load "$AGENTS_DIR/com.squeegeeguy.leadgen.plist"

echo "Installed and loaded com.squeegeeguy.leadgen."
echo "It will run daily at 7:00 AM."
echo ""
echo "To trigger immediately:  launchctl start com.squeegeeguy.leadgen"
echo "To unload:               launchctl unload ~/Library/LaunchAgents/com.squeegeeguy.leadgen.plist"
echo "To watch logs:           tail -f /tmp/squeegeeguy-leadgen.log"
