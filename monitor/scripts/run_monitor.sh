#!/bin/bash
# -------------------------
# Run Monitor Module & Ensure Bot Runs in Background (with auto-restart)
# -------------------------

set -euo pipefail

# -------------------------
# Set project base directory dynamically
BASE_DIR="$(realpath "$(dirname "$0")/../..")"
CONFIG_FILE="$BASE_DIR/setup/config.json"

# -------------------------
# Paths from config.json
SCRIPT_REL_PATH="$(jq -r '.paths.monitor.script' "$CONFIG_FILE")"
LOGS_REL_PATH="$(jq -r '.paths.monitor.logs' "$CONFIG_FILE")"
STATE_REL_PATH="$(jq -r '.paths.monitor.state' "$CONFIG_FILE")"
VENV_REL_PATH="$(jq -r '.paths.venv_dir' "$CONFIG_FILE")"
BOT_REL_PATH="$(jq -r '.paths.monitor.script' "$CONFIG_FILE" | sed 's/monitor\.py/monitor_bot.py/')"

# Resolve absolute paths
SCRIPT_PATH="$BASE_DIR/$SCRIPT_REL_PATH"
LOGS_DIR="$BASE_DIR/$LOGS_REL_PATH"
STATE_DIR="$BASE_DIR/$STATE_REL_PATH"
VENV_DIR="$BASE_DIR/$VENV_REL_PATH"
BOT_SCRIPT="$BASE_DIR/$BOT_REL_PATH"

mkdir -p "$LOGS_DIR" "$STATE_DIR"

LOG_FILE="$LOGS_DIR/run_monitor_$(date '+%Y-%m-%d').log"
BOT_LOG_FILE="$LOGS_DIR/monitor_bot.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log "=== Starting Monitor Module ==="

# -------------------------
# Activate virtual environment
if [[ -f "$VENV_DIR/bin/activate" ]]; then
    source "$VENV_DIR/bin/activate"
else
    log "ERROR: Virtual environment not found at $VENV_DIR"
    exit 1
fi

# -------------------------
# Run the monitor script once
log "Running monitor.py..."
"$VENV_DIR/bin/python" "$SCRIPT_PATH" --config "$CONFIG_FILE" "$@"
log "Finished monitor.py run."

# -------------------------
# Stop any existing monitor_bot.py
if pgrep -f "$BOT_SCRIPT" > /dev/null; then
    log "Stopping existing monitor_bot.py..."
    pkill -f "$BOT_SCRIPT" || true
    sleep 2
fi

# -------------------------
# Run monitor_bot.py in the background with auto-restart
log "Starting monitor_bot.py in background..."
nohup bash -c "
    while true; do
        echo \"\$(date '+%Y-%m-%d %H:%M:%S') - Starting monitor_bot.py...\" >> \"$BOT_LOG_FILE\"
        \"$VENV_DIR/bin/python\" \"$BOT_SCRIPT\" --config \"$CONFIG_FILE\" >> \"$BOT_LOG_FILE\" 2>&1
        echo \"\$(date '+%Y-%m-%d %H:%M:%S') - monitor_bot.py crashed or exited. Restarting in 5s...\" >> \"$BOT_LOG_FILE\"
        sleep 5
    done
" >/dev/null 2>&1 &
log "monitor_bot.py wrapper started in background with PID $!"

# -------------------------
# Cronjob (every minute) for monitor.py
CRON_SCHEDULE="* * * * *"
CRON_CMD="$VENV_DIR/bin/python $SCRIPT_PATH --config $CONFIG_FILE"
(crontab -l 2>/dev/null | grep -F -q "$CRON_CMD") || {
    (crontab -l 2>/dev/null; echo "$CRON_SCHEDULE $CRON_CMD") | crontab -
    log "Cron job added: runs monitor.py every minute"
}

# -------------------------
# Deactivate virtualenv
deactivate
log "=== Monitor Module Completed ==="

