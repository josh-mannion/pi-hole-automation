#!/bin/bash
# -------------------------
# Run Monitor Module & Setup Bot Autostart
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
# Run the monitor script
"$VENV_DIR/bin/python" "$SCRIPT_PATH" --config "$CONFIG_FILE" "$@"

log "=== Finished Monitor Module ==="

# -------------------------
# Setup systemd service for bot if not already exists
SERVICE_FILE="/etc/systemd/system/monitor_bot.service"
if [[ ! -f "$SERVICE_FILE" ]]; then
    sudo bash -c "cat > $SERVICE_FILE" <<EOL
[Unit]
Description=Pi-hole Monitor Telegram Bot
After=network.target

[Service]
User=$(whoami)
WorkingDirectory=$BASE_DIR
ExecStart=$VENV_DIR/bin/python $BOT_SCRIPT --config $CONFIG_FILE
Restart=always
RestartSec=10
Environment="PATH=$VENV_DIR/bin:/usr/bin:/bin"
StandardOutput=append:$BOT_LOG_FILE
StandardError=append:$BOT_LOG_FILE

[Install]
WantedBy=multi-user.target
EOL

    # Reload systemd, enable and start the service
    sudo systemctl daemon-reload
    sudo systemctl enable monitor_bot.service
    sudo systemctl start monitor_bot.service
    log "Monitor bot systemd service created, enabled, and started."
else
    log "Monitor bot systemd service already exists."
fi

# -------------------------
# Cronjob (every minute) for monitor.py
CRON_SCHEDULE="* * * * *"
CRON_CMD="$VENV_DIR/bin/python $SCRIPT_PATH --config $CONFIG_FILE"

# Add cron if it does not already exist
(crontab -l 2>/dev/null | grep -F -q "$CRON_CMD") || {
    (crontab -l 2>/dev/null; echo "$CRON_SCHEDULE $CRON_CMD") | crontab -
    log "Cron job added: runs monitor every minute"
}

# -------------------------
# Deactivate virtualenv
deactivate
