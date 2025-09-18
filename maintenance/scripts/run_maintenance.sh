#!/bin/bash
# -------------------------
# Run Maintenance Module
# -------------------------

set -euo pipefail

# -------------------------
# Set project base directory dynamically
BASE_DIR="$(realpath "$(dirname "$0")/../..")"
CONFIG_FILE="$BASE_DIR/setup/config.json"

# -------------------------
# Load paths from config.json
SCRIPT_REL_PATH="$(jq -r '.paths.maintenance.script' "$CONFIG_FILE")"
SCRIPT_PATH="$BASE_DIR/$SCRIPT_REL_PATH"

LOGS_REL_PATH="$(jq -r '.paths.maintenance.logs' "$CONFIG_FILE")"
LOGS_DIR="$BASE_DIR/$LOGS_REL_PATH"

STATE_REL_PATH="$(jq -r '.paths.maintenance.state' "$CONFIG_FILE")"
STATE_DIR="$BASE_DIR/$STATE_REL_PATH"

VENV_REL_PATH="$(jq -r '.paths.venv_dir' "$CONFIG_FILE")"
VENV_DIR="$BASE_DIR/$VENV_REL_PATH"

mkdir -p "$LOGS_DIR" "$STATE_DIR"

LOG_FILE="$LOGS_DIR/run_maintenance_$(date '+%Y-%m-%d').log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log "=== Starting Maintenance Module ==="

# -------------------------
# Activate virtual environment
VENV_ACTIVATE="$VENV_DIR/bin/activate"
if [[ -f "$VENV_ACTIVATE" ]]; then
    # shellcheck disable=SC1090
    source "$VENV_ACTIVATE"
else
    log "ERROR: Virtual environment not found at $VENV_ACTIVATE"
    exit 1
fi

# -------------------------
# Run the maintenance script
PYTHON_BIN="$VENV_DIR/bin/python"
"$PYTHON_BIN" "$SCRIPT_PATH" --config "$CONFIG_FILE" "$@"
deactivate

log "=== Finished Maintenance Module ==="

# -------------------------
# Cronjobs setup
add_cron() {
    local schedule="$1"
    local task="$2"
    local cmd="$PYTHON_BIN $SCRIPT_PATH --config $CONFIG_FILE --task $task"
    if ! crontab -l 2>/dev/null | grep -F -q "$cmd"; then
        (crontab -l 2>/dev/null; echo "$schedule $cmd") | crontab -
        log "Cron job added: $task scheduled at '$schedule'"
    else
        log "Cron job already exists: $task"
    fi
}

# Weekly gravity update: Sunday 03:00
add_cron "0 3 * * 0" "gravity"

# Monthly OS update & upgrade: 1st of the month at 04:00
add_cron "0 4 1 * *" "os_update"

# Monthly Pi-hole update: 2nd of the month at 04:30
add_cron "30 4 2 * *" "pihole_update"

# Yearly Pi-hole query log flush: Jan 1st at 05:00
add_cron "0 5 1 1 *" "clear_logs"
