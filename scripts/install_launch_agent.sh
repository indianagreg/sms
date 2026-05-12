#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
LOAD_AGENT=1
if [ "${1:-}" = "--no-load" ]; then
  LOAD_AGENT=0
fi

APP_DIR="${SMS_FOLLOWUP_HOME:-$HOME/.sms-followup}"
LABEL="${SMS_FOLLOWUP_LABEL:-com.sms-followup.daily}"
CONFIG="$APP_DIR/config.json"
ENV_FILE="$APP_DIR/.env"
RUNNER="$PROJECT_DIR/scripts/run_daily.sh"
TEMPLATE="$PROJECT_DIR/launchd/com.sms-followup.daily.plist.template"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
OUT_LOG="$HOME/Library/Logs/sms-followup.out.log"
ERR_LOG="$HOME/Library/Logs/sms-followup.err.log"
LEGACY_DEST="$HOME/Library/LaunchAgents/com.greg.sms-followup.plist"

mkdir -p "$APP_DIR" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"

if [ ! -f "$CONFIG" ]; then
  cp "$PROJECT_DIR/config.example.json" "$CONFIG"
  echo "Created config template: $CONFIG"
fi

if [ ! -f "$ENV_FILE" ]; then
  cat > "$ENV_FILE" <<'EOF'
SMS_FOLLOWUP_SMTP_PASSWORD=""
OPENAI_API_KEY=""
EOF
  chmod 600 "$ENV_FILE"
  echo "Created secrets template: $ENV_FILE"
fi

sed \
  -e "s#__LABEL__#$LABEL#g" \
  -e "s#__RUNNER__#$RUNNER#g" \
  -e "s#__CONFIG__#$CONFIG#g" \
  -e "s#__PROJECT_DIR__#$PROJECT_DIR#g" \
  -e "s#__OUT_LOG__#$OUT_LOG#g" \
  -e "s#__ERR_LOG__#$ERR_LOG#g" \
  "$TEMPLATE" > "$DEST"

if [ "$LOAD_AGENT" -eq 1 ]; then
  if [ "$DEST" != "$LEGACY_DEST" ] && [ -f "$LEGACY_DEST" ]; then
    launchctl unload "$LEGACY_DEST" 2>/dev/null || true
    rm -f "$LEGACY_DEST"
    echo "Removed legacy LaunchAgent: $LEGACY_DEST"
  fi
  launchctl unload "$DEST" 2>/dev/null || true
  launchctl load "$DEST"
fi
echo "Installed daily SMS follow-up digest LaunchAgent: $DEST"
echo "Edit config: $CONFIG"
echo "Edit secrets: $ENV_FILE"
