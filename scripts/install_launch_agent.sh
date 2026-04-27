#!/bin/sh
set -eu

SOURCE="/Users/greg/sms/launchd/com.greg.sms-followup.plist"
DEST="$HOME/Library/LaunchAgents/com.greg.sms-followup.plist"

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
cp "$SOURCE" "$DEST"
launchctl unload "$DEST" 2>/dev/null || true
launchctl load "$DEST"
echo "Installed daily SMS follow-up digest LaunchAgent: $DEST"
