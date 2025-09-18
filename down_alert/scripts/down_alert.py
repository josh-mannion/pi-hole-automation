#!/usr/bin/env python3
"""
Down Alert Module for Pi-hole Automation
- Checks Pi-hole FTL status and internet connectivity
- Sends Telegram alerts only on status change
- Uses a state file to prevent spamming
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
import requests
import argparse

# -------------------------
# Arguments
parser = argparse.ArgumentParser(description="Down Alert for Pi-hole Automation")
parser.add_argument("--config", type=str, required=True, help="Path to config.json")
parser.add_argument("--test", action="store_true", help="Enable test mode (no Telegram alerts)")
args = parser.parse_args()
TEST_MODE = args.test

# -------------------------
# Load config
CONFIG_FILE = Path(args.config).resolve()
if not CONFIG_FILE.exists():
    raise FileNotFoundError(f"Config file not found: {CONFIG_FILE}")

with open(CONFIG_FILE) as f:
    config = json.load(f)

BOT_TOKEN = config["telegram"]["bot_token"]
CHAT_ID = config["telegram"]["chat_id"]

# -------------------------
# Paths from config
BASE_DIR = (CONFIG_FILE.parent.parent).resolve()
DOWN_ALERT_PATHS = config["paths"]["down_alert"]

LOGS_DIR = (BASE_DIR / DOWN_ALERT_PATHS["logs"]).resolve()
STATE_DIR = (BASE_DIR / DOWN_ALERT_PATHS["state"]).resolve()

LOGS_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOGS_DIR / f"down_alert_{datetime.now().strftime('%Y-%m-%d')}.log"
STATE_FILE = STATE_DIR / "down_alert_state.json"

# -------------------------
# Logging
def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[Down Alert] {timestamp} - {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# -------------------------
# State management
def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"pihole_status": "unknown", "internet": True}  # default internet True to prevent first-run alert

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# -------------------------
# Checks
def check_pihole() -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "pihole-FTL"],
            capture_output=True, text=True
        )
        return result.stdout.strip() == "active"
    except Exception as e:
        log(f"Error checking Pi-hole FTL service: {e}")
        return False

def check_internet() -> bool:
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "2", "1.1.1.1"],
            capture_output=True
        )
        return result.returncode == 0
    except Exception as e:
        log(f"Error checking internet: {e}")
        return False

# -------------------------
# Telegram Alerts
def send_telegram(msg: str):
    if TEST_MODE:
        log(f"[TEST MODE] Telegram alert: {msg}")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            log(f"Failed to send Telegram alert: {response.text}")
    except Exception as e:
        log(f"Failed to send Telegram alert: {e}")

# -------------------------
# Main Logic
state = load_state()
current_pihole = check_pihole()
current_internet = check_internet()

alerts = []

# Pi-hole status change
if state.get("pihole_status") != ("up" if current_pihole else "down"):
    alerts.append("✅ Pi-hole is BACK UP!" if current_pihole else "⚠️ Pi-hole is DOWN!")
    state["pihole_status"] = "up" if current_pihole else "down"

# Internet status change
if state.get("internet") != current_internet:
    alerts.append("✅ Internet connection RESTORED!" if current_internet else "⚠️ Internet connection LOST!")
    state["internet"] = current_internet

# Send alerts
if alerts:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for msg in alerts:
        full_msg = f"{msg}\nTimestamp: {timestamp}"
        send_telegram(full_msg)
        log(f"Telegram alert sent: {full_msg}")
else:
    log("No change in Pi-hole or internet status.")

save_state(state)
