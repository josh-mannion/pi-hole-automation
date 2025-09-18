#!/bin/bash

# ----------------------------------------
# Initial Setup for Pi-hole Automation
# ----------------------------------------

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$BASE_DIR/venv"
REQUIREMENTS_FILE="$BASE_DIR/setup/requirements.txt"
CONFIG_FILE="$BASE_DIR/setup/config.json"

echo "Starting initial setup for Pi-hole Automation..."

# -------------------------
# Check Python3
# -------------------------
if ! command -v python3 &>/dev/null; then
    echo "Python3 not found. Please install Python3."
    exit 1
fi

# -------------------------
# Stop monitor_bot.py if running
# -------------------------
MONITOR_BOT_SCRIPT="$BASE_DIR/monitor/scripts/monitor_bot.py"
MONITOR_BOT_PID=$(pgrep -f "$MONITOR_BOT_SCRIPT" || true)

if [ -n "$MONITOR_BOT_PID" ]; then
    echo "[INFO] monitor_bot.py is currently running (PID: $MONITOR_BOT_PID). Stopping temporarily..."
    kill "$MONITOR_BOT_PID"
else
    echo "[INFO] monitor_bot.py is not running."
fi

# -------------------------
# Virtual Environment Setup / Update
# -------------------------
if [ -d "$VENV_DIR" ]; then
    echo "[INFO] Virtual environment exists at $VENV_DIR. Updating..."
    # shellcheck disable=SC1090
    source "$VENV_DIR/bin/activate"
    python -m pip install --upgrade pip
    if [ -f "$REQUIREMENTS_FILE" ]; then
        python -m pip install --upgrade -r "$REQUIREMENTS_FILE"
    fi
else
    echo "[INFO] Creating virtual environment at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
    # shellcheck disable=SC1090
    source "$VENV_DIR/bin/activate"
    python -m pip install --upgrade pip
    if [ -f "$REQUIREMENTS_FILE" ]; then
        python -m pip install -r "$REQUIREMENTS_FILE"
    fi
fi

# -------------------------
# Create required folders
# -------------------------
echo "Ensuring folder structure..."
REQUIRED_FOLDERS=(
    "down_alert/logs"
    "down_alert/state"
    "maintenance/logs"
    "maintenance/state"
    "monitor/logs"
    "monitor/state"
    "setup"
    "venv"
)
for folder in "${REQUIRED_FOLDERS[@]}"; do
    mkdir -p "$BASE_DIR/$folder"
done

# -------------------------
# Create config file if missing or empty
# -------------------------
if [ ! -s "$CONFIG_FILE" ]; then
    echo "Creating default configuration file..."
    mkdir -p "$(dirname "$CONFIG_FILE")"
    cat <<EOF > "$CONFIG_FILE"
{
  "telegram": {
    "bot_token": "",
    "chat_id": ""
  },
  "paths": {
    "base_dir": "$BASE_DIR",
    "venv_dir": "$VENV_DIR",
    "requirements_file": "$REQUIREMENTS_FILE",
    "down_alert": {
      "logs": "$BASE_DIR/down_alert/logs",
      "state": "$BASE_DIR/down_alert/state",
      "script": "$BASE_DIR/down_alert/scripts/down_alert.py"
    },
    "maintenance": {
      "logs": "$BASE_DIR/maintenance/logs",
      "state": "$BASE_DIR/maintenance/state",
      "script": "$BASE_DIR/maintenance/scripts/maintenance.py"
    },
    "monitor": {
      "logs": "$BASE_DIR/monitor/logs",
      "state": "$BASE_DIR/monitor/state",
      "script": "$BASE_DIR/monitor/scripts/monitor.py"
    }
  },
  "settings": {
    "docker_test": false,
    "dry_run": false
  }
}
EOF
fi

# -------------------------
# Ask if user wants to use Telegram
# -------------------------
read -rp "Do you want to use a Telegram bot for notifications? (Y/N): " USE_TELEGRAM
USE_TELEGRAM="${USE_TELEGRAM^^}"

if [ "$USE_TELEGRAM" == "Y" ]; then
    echo "Please send a message to your bot in Telegram (e.g., /start) before continuing."
    read -rp "Enter Telegram Bot Token: " TELEGRAM_TOKEN

    # -------------------------
    # Detect chat ID using Python
    # -------------------------
    python3 - <<END
import json, sys, time, requests

token = "$TELEGRAM_TOKEN"
chat_id = None

for _ in range(30):  # ~1 minute
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=5).json()
        if "result" in r and r["result"]:
            chat_id = r["result"][-1]["message"]["chat"]["id"]
            break
    except Exception:
        pass
    time.sleep(2)

if chat_id is None:
    print("No messages detected from the bot. Please send a message and run setup again.")
    sys.exit(1)

# Update config.json
with open("$CONFIG_FILE", "r+") as f:
    config = json.load(f)
    config["telegram"]["bot_token"] = token
    config["telegram"]["chat_id"] = str(chat_id)
    f.seek(0)
    json.dump(config, f, indent=2)
    f.truncate()

print(f"Telegram bot token and chat ID updated in config.json: {chat_id}")
END

else
    echo "[INFO] Skipping Telegram bot setup. Modules will run without notifications."
fi

# -------------------------
# Prompt to install/run modules
# -------------------------
declare -a MODULES=("down_alert" "maintenance" "monitor")
declare -a REMAINING_MODULES=()

read -rp "Do you want to run install_all.sh now? (Y/N): " INSTALL_ALL
INSTALL_ALL="${INSTALL_ALL^^}"

if [ "$INSTALL_ALL" == "Y" ]; then
    bash "$BASE_DIR/setup/install_all.sh"
else
    for MODULE in "${MODULES[@]}"; do
        read -rp "Install $MODULE? (Y/N): " ANSWER
        ANSWER="${ANSWER^^}"
        if [ "$ANSWER" == "Y" ]; then
            bash "$BASE_DIR/$MODULE/scripts/run_${MODULE}.sh"
        else
            REMAINING_MODULES+=("$MODULE")
        fi
    done

    if [ "${#REMAINING_MODULES[@]} -gt 0" ]; then
        echo
        echo "Modules not installed during setup: ${REMAINING_MODULES[*]}"
        echo "To install remaining modules later, run:"
        for MODULE in "${REMAINING_MODULES[@]}"; do
            echo "bash $BASE_DIR/$MODULE/scripts/run_${MODULE}.sh"
        done
        echo
    fi
fi

# -------------------------
# Deactivate venv
# -------------------------
deactivate || true
echo "Initial setup finished successfully!"
