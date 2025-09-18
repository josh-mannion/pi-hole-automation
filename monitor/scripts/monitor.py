#!/usr/bin/env python3
"""
Monitor Module for Pi-hole Automation
- Measures CPU, RAM, Disk, and CPU Temp
- Sends Telegram alerts if thresholds are exceeded
- Saves metrics and alert flags to state file
"""

import json
from pathlib import Path
from datetime import datetime
import psutil
import argparse
import subprocess
import requests
import sys

# -------------------------
# Arguments
parser = argparse.ArgumentParser(description="Monitor Module for Pi-hole Automation")
parser.add_argument("--config", type=str, required=True, help="Path to config.json")
parser.add_argument("--test", action="store_true", help="Enable test mode (no Telegram alerts)")
parser.add_argument("--force", action="store_true", help="Force a check and alert even if already alerted")
args = parser.parse_args()
TEST_MODE = args.test
FORCE_CHECK = args.force

# -------------------------
# Load Config
CONFIG_FILE = Path(args.config).resolve()
if not CONFIG_FILE.exists():
    print(f"[ERROR] Config file not found: {CONFIG_FILE}")
    sys.exit(1)

with open(CONFIG_FILE) as f:
    config = json.load(f)

BOT_TOKEN = config.get("telegram", {}).get("bot_token")
CHAT_ID = config.get("telegram", {}).get("chat_id")

BASE_DIR = CONFIG_FILE.parent.parent

# -------------------------
# Paths from config
MONITOR_CONFIG = config.get("paths", {}).get("monitor", {})
LOGS_DIR = Path(BASE_DIR) / MONITOR_CONFIG.get("logs", "")
STATE_DIR = Path(BASE_DIR) / MONITOR_CONFIG.get("state", "")

if not LOGS_DIR or not STATE_DIR:
    print("[ERROR] Monitor paths missing in config.json")
    sys.exit(1)

LOGS_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOGS_DIR / f"monitor_{datetime.now().strftime('%Y-%m-%d')}.log"
STATE_FILE = STATE_DIR / "monitor_state.json"

# -------------------------
# Thresholds
THRESHOLDS = {
    "cpu": 85,    # %
    "ram": 90,    # %
    "disk": 90,   # %
    "temp": 75    # °C
}

# -------------------------
# Logging
def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[Monitor] {timestamp} - {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# -------------------------
# Telegram Alerts
def send_telegram(msg: str):
    if TEST_MODE:
        log(f"[TEST MODE] Telegram alert: {msg}")
        return
    if not BOT_TOKEN or not CHAT_ID:
        log("Telegram credentials missing. Skipping alert.")
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
# System Metrics
def get_metrics():
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    temp_c = None

    try:
        temps = psutil.sensors_temperatures()
        coretemp = temps.get('coretemp', [])
        if coretemp:
            temp_c = coretemp[0].current
        else:
            # Fallback for Raspberry Pi
            result = subprocess.run(['vcgencmd', 'measure_temp'], capture_output=True, text=True)
            if result.returncode == 0 and "temp=" in result.stdout:
                temp_c = float(result.stdout.strip().replace("temp=", "").replace("'C",""))
    except Exception:
        temp_c = None

    return {"cpu": cpu, "ram": ram, "disk": disk, "temp": temp_c}

# -------------------------
# Load/Save State
def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"metrics": {}, "alerts": {}, "last_check": None}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# -------------------------
# Check Thresholds & Alerts
def check_alerts(metrics, prev_alerts):
    alerts = {}
    send_alert = False
    msg_lines = ["⚠️ Monitor Alert"]

    for key, value in metrics.items():
        threshold = THRESHOLDS.get(key)
        if value is not None and value > threshold:
            alerts[key] = True
            if FORCE_CHECK or not prev_alerts.get(key, False):
                send_alert = True
            msg_lines.append(f"{key.upper()}: {value}% (Threshold: {threshold}%)")
        else:
            alerts[key] = False

    return send_alert, alerts, "\n".join(msg_lines)

# -------------------------
# Main
def main():
    metrics = get_metrics()
    state = load_state()
    prev_alerts = state.get("alerts", {})

    send_alert, alerts, alert_msg = check_alerts(metrics, prev_alerts)

    state.update({
        "metrics": metrics,
        "alerts": alerts,
        "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_state(state)

    if send_alert:
        send_telegram(alert_msg)
        log(f"Alert sent: {alert_msg}")
    else:
        log(f"No thresholds exceeded. Metrics: {metrics}")

if __name__ == "__main__":
    main()
