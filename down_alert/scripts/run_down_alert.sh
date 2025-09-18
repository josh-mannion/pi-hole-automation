#!/bin/bash
# -------------------------
# Run Down Alert Module
# -------------------------

set -euo pipefail

# -------------------------
# Set project base directory dynamically
# -------------------------
BASE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
CONFIG_FILE="$BASE_DIR/setup/config.json"

# -------------------------
# Load paths from config.json
# -------------------------
VENV_DIR_REL="$(jq -r '.paths.venv_dir' "$CONFIG_FILE")"
SCRIPT_REL_PATH="$(jq -r '.paths.down_alert.script' "$CONFIG_FILE")"
LOGS_REL_PATH="$(jq -r '.paths.down_alert.logs' "$CONFIG_FILE")"

VENV_PATH="$BASE_DIR/$VENV_DIR_REL"
SCRIPT_PATH="$BASE_DIR/$SCRIPT_REL_PATH"
LOGS_DIR="$BASE_DIR/$LOGS_REL_PATH"
mkdir -p "$LOGS_DIR"

LOG_FILE="$LOGS_DIR/run_down_alert_$(date '+%Y-%m-%d').log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log "=== Starting Down Alert Module ==="

# -------------------------
# Activate virtual environment
# -------------------------
VENV_ACTIVATE="$VENV_PATH/bin/activate"
if [[ -f "$VENV_ACTIVATE" ]]; then
    # shellcheck disable=SC1090
    source "$VENV_ACTIVATE"
else
    log "ERROR: Virtual environment not found at $VENV_ACTIVATE"
    exit 1
fi

# -------------------------
# Run the down_alert Python script
# -------------------------
PYTHON_BIN="$VENV_PATH/bin/python"
"$PYTHON_BIN" "$SCRIPT_PATH" --config "$CONFIG_FILE" "$@"

deactivate
log "=== Finished Down Alert Module ==="

# -------------------------
# Cronjob (every 1 minute)
# -------------------------
CRON_CMD="$PYTHON_BIN $SCRIPT_PATH --config $CONFIG_FILE >> $LOGS_DIR/cron.log 2>&1"
if ! crontab -l 2>/dev/null | grep -F -q "$SCRIPT_PATH"; then
    (crontab -l 2>/dev/null; echo "*/1 * * * * $CRON_CMD") | crontab -
    log "Cron job added: runs down_alert every minute"
fi
