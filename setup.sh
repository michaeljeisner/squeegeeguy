#!/usr/bin/env bash
# Installs two launchd jobs:
#   com.squeegeeguy.leadgen  — full pipeline, daily at 7:00 AM
#   com.squeegeeguy.replies  — reply/booking agent, every 15 minutes
# Paths are generated from wherever this repo lives, so it works on any Mac.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_DIR="$HOME/Library/LaunchAgents"
UV_BIN="$(command -v uv || echo /opt/homebrew/bin/uv)"

mkdir -p "$AGENTS_DIR"

write_plist() {
  local label="$1" script="$2" schedule_xml="$3" out="$AGENTS_DIR/$1.plist"
  cat > "$out" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${UV_BIN}</string>
        <string>run</string>
        <string>python</string>
        <string>${script}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
${schedule_xml}
    <key>StandardOutPath</key>
    <string>/tmp/${label}.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/${label}.err</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF
  launchctl unload "$out" 2>/dev/null || true
  launchctl load "$out"
  echo "Installed and loaded ${label}"
}

DAILY_SCHEDULE='    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>7</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>'

REPLIES_SCHEDULE='    <key>StartInterval</key>
    <integer>900</integer>'

write_plist "com.squeegeeguy.leadgen" "run.py" "$DAILY_SCHEDULE"
write_plist "com.squeegeeguy.replies" "checkin.py" "$REPLIES_SCHEDULE"

echo ""
echo "Daily pipeline runs at 7:00 AM; reply/booking agent runs every 15 minutes."
echo ""
echo "Trigger pipeline now:   launchctl start com.squeegeeguy.leadgen"
echo "Trigger replies now:    launchctl start com.squeegeeguy.replies"
echo "Watch logs:             tail -f /tmp/com.squeegeeguy.leadgen.log /tmp/com.squeegeeguy.replies.log"
echo "Uninstall:              launchctl unload ~/Library/LaunchAgents/com.squeegeeguy.*.plist"
