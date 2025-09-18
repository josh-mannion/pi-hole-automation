#!/usr/bin/env python3
"""
Maintenance Module for Pi-hole Automation
- Performs OS updates, Pi-hole updates, Gravity updates, and log cleanup (flush Pi-hole logs)
- Logs all actions and saves state
- Sends Telegram summary alerts
- Uses paths from config.json, including venv Python executable
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
import argparse
import sys
import requests

# -------------------------
# Arguments
parser = argparse.ArgumentParser(description="Maintenance Module for Pi-hole Automation")
parser.add_argument("--task", default="all",
                    choices=["all", "os_update", "gravity", "pihole_update", "clear_logs"],
                    help="Specify a maintenance task to run")
parser.add_argument("--config", type=str, required=True, help="Path to config.json")
parser.add_argument("--test", action="store_true", help="Enable test mode (no Telegram alerts)")
args = parser.parse_args()

TASK = args.task
TEST_MODE = args.test

# -------------------------
# Load Config & Paths
CONFIG_FILE = Path(args.config).resolve()
if not CONFIG_FILE.exists():
    print(f"[ERROR] Config file not found: {CONFIG_FILE}")
    sys.exit(1)

with open(CONFIG_FILE) as f:
    config = json.load(f)

BOT_TOKEN = config.get("telegram", {}).get("bot_token")
CHAT_ID = config.get("telegram", {}).get("chat_id")

if not BOT_TOKEN or not CHAT_ID:
    print("[WARNING] Telegram bot token or chat ID missing. Telegram alerts will be disabled.")
    TEST_MODE = True

# -------------------------
# Paths from config
BASE_DIR = CONFIG_FILE.parent.parent.resolve()
STATE_DIR = (BASE_DIR / config["paths"]["maintenance"]["state"]).resolve()
LOGS_DIR = (BASE_DIR / config["paths"]["maintenance"]["logs"]).resolve()
STATE_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOGS_DIR / f"maintenance_{datetime.now().strftime('%Y-%m-%d')}.log"
STATE_FILE = STATE_DIR / "maintenance_state.json"

# Venv Python executable
VENV_DIR = (BASE_DIR / config["paths"]["venv_dir"]).resolve()
PYTHON_BIN = VENV_DIR / "bin/python"

# -------------------------
# Logging
def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[Maintenance] {timestamp} - {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# -------------------------
# Telegram Alerts
def send_telegram(msg: str):
    if TEST_MODE:
        log(f"[TEST MODE] Telegram alert: {msg}")
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg}
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            log(f"Failed to send Telegram alert: {response.text}")
    except Exception as e:
        log(f"Failed to send Telegram alert: {e}")

# -------------------------
# State Management
def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}

def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

state = load_state()

# -------------------------
# System Maintenance Functions
def run_command(cmd, description):
    """
    Run a command using the venv Python executable if it's a Python script, otherwise use shell.
    """
    log(f"Starting: {description}")
    try:
        # Use subprocess with shell=True for system commands (apt, pihole)
        process = subprocess.Popen(
            cmd, shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        output_lines = []
        for line in process.stdout:
            print(line, end="")  # live console feedback
            with open(LOG_FILE, "a") as f:
                f.write(line)  # raw command output also logged
            output_lines.append(line.strip())

        process.wait()
        if process.returncode != 0:
            log(f"ERROR running {description} (exit code {process.returncode})")
            return False, "\n".join(output_lines)

        log(f"Completed: {description}")
        return True, "\n".join(output_lines)

    except Exception as e:
        log(f"Exception running {description}: {e}")
        return False, str(e)

def os_update():
    return run_command("sudo apt update && sudo apt upgrade -y", "OS update & upgrade")

def pihole_update():
    return run_command("sudo pihole -up", "Pi-hole update")

def gravity_update():
    return run_command("sudo pihole -g", "Pi-hole gravity update")

def clear_logs():
    return run_command("sudo pihole flush", "Flush Pi-hole query logs")

# -------------------------
# Task Runner
results = {}
tasks_to_run = {
    "os_update": os_update,
    "pihole_update": pihole_update,
    "gravity": gravity_update,
    "clear_logs": clear_logs
}

if TASK == "all":
    for t_name, func in tasks_to_run.items():
        success, msg = func()
        results[t_name] = {"success": success, "output": msg}
else:
    func = tasks_to_run.get(TASK)
    if func:
        success, msg = func()
        results[TASK] = {"success": success, "output": msg}

# -------------------------
# Update State & Send Summary
for task_name, result in results.items():
    state[task_name] = {
        "last_run": datetime.now().isoformat(),
        "success": result["success"],
        "output": result["output"]
    }

save_state(state)

summary_lines = [f"{t}: {'✅ Success' if r['success'] else '❌ Failed'}" for t, r in results.items()]
summary_msg = f"Maintenance Summary ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}):\n" + "\n".join(summary_lines)
send_telegram(summary_msg)
log("=== Maintenance Module Finished ===")
