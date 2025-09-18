#!/usr/bin/env python3
"""
Merged Telegram Bot for Monitor + Maintenance Modules
- Monitor: reports system metrics (live check optional)
- Maintenance: runs maintenance tasks via inline buttons, logs output, tracks state
- All paths are fully config-driven
"""

import json
from pathlib import Path
import asyncio
import subprocess
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# -------------------------
# Base paths & config
BASE_DIR = Path(__file__).resolve().parents[2]  # two levels up from scripts/
CONFIG_FILE = BASE_DIR / "setup/config.json"

if not CONFIG_FILE.exists():
    raise FileNotFoundError(f"Config file not found: {CONFIG_FILE}")

with open(CONFIG_FILE) as f:
    config = json.load(f)

# -------------------------
# Telegram bot token
BOT_TOKEN = config.get("telegram", {}).get("bot_token")
if not BOT_TOKEN:
    raise ValueError("Telegram bot token missing in config.json")

# -------------------------
# Monitor paths & state
MONITOR_CONFIG = config.get("paths", {}).get("monitor")
if not MONITOR_CONFIG or "script" not in MONITOR_CONFIG or "state" not in MONITOR_CONFIG:
    raise ValueError("Monitor paths missing in config.json")

MONITOR_SCRIPT = BASE_DIR / MONITOR_CONFIG["script"]
if not MONITOR_SCRIPT.exists():
    raise FileNotFoundError(f"Monitor script not found: {MONITOR_SCRIPT}")

STATE_DIR_MONITOR = BASE_DIR / MONITOR_CONFIG["state"]
STATE_DIR_MONITOR.mkdir(parents=True, exist_ok=True)
STATE_FILE_MONITOR = STATE_DIR_MONITOR / "monitor_state.json"

# Optional: monitor logs directory
LOGS_DIR_MONITOR = BASE_DIR / MONITOR_CONFIG.get("logs", "monitor/logs")
LOGS_DIR_MONITOR.mkdir(parents=True, exist_ok=True)

# -------------------------
# Maintenance paths & state
MAINT_CONFIG = config.get("paths", {}).get("maintenance")
if not MAINT_CONFIG or "script" not in MAINT_CONFIG or "logs" not in MAINT_CONFIG or "state" not in MAINT_CONFIG:
    raise ValueError("Maintenance paths missing in config.json")

MAINT_SCRIPT = BASE_DIR / MAINT_CONFIG["script"]
if not MAINT_SCRIPT.exists():
    raise FileNotFoundError(f"Maintenance script not found: {MAINT_SCRIPT}")

LOGS_DIR_MAINT = BASE_DIR / MAINT_CONFIG["logs"]
LOGS_DIR_MAINT.mkdir(parents=True, exist_ok=True)

STATE_DIR_MAINT = BASE_DIR / MAINT_CONFIG["state"]
STATE_DIR_MAINT.mkdir(parents=True, exist_ok=True)
STATE_FILE_MAINT = STATE_DIR_MAINT / "maintenance_state.json"

# -------------------------
# Virtualenv python
VENV_DIR = BASE_DIR / config.get("paths", {}).get("venv_dir")
if not VENV_DIR or not (VENV_DIR / "bin/python").exists():
    raise FileNotFoundError(f"Virtual environment python not found at {VENV_DIR}/bin/python")
VENV_PYTHON = VENV_DIR / "bin/python"

# -------------------------
# ---------- Monitor Functions ----------
async def run_live_check():
    """Run monitor.py with --force to update metrics"""
    try:
        process = await asyncio.create_subprocess_exec(
            str(VENV_PYTHON),
            str(MONITOR_SCRIPT),
            "--config", str(CONFIG_FILE),
            "--force",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            print(f"[Monitor Bot] Live check failed: {stderr.decode().strip()}")
            return False
        return True
    except Exception as e:
        print(f"[Monitor Bot] Exception during live check: {e}")
        return False

def load_monitor_state():
    if STATE_FILE_MONITOR.exists():
        with open(STATE_FILE_MONITOR) as f:
            return json.load(f)
    return {}

def format_metrics(state):
    metrics = state.get("metrics", {})
    last_check = state.get("last_check", "N/A")
    return (f"📊 Current System Metrics (Last checked: {last_check})\n"
            f"CPU: {metrics.get('cpu', 'N/A')}%\n"
            f"RAM: {metrics.get('ram', 'N/A')}%\n"
            f"Disk: {metrics.get('disk', 'N/A')}%\n"
            f"Temp: {metrics.get('temp', 'N/A')}°C")

# -------------------------
# ---------- Maintenance Functions ----------
def log_task(task_name: str, message: str) -> Path:
    """Write task output to a log file and return path"""
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    log_file = LOGS_DIR_MAINT / f"{task_name}_{timestamp}.log"
    with open(log_file, "a") as f:
        f.write(message + "\n")
    return log_file

def load_maint_state() -> dict:
    if STATE_FILE_MAINT.exists():
        with open(STATE_FILE_MAINT) as f:
            return json.load(f)
    return {}

def save_maint_state(task_name: str, success: bool, output: str):
    state = load_maint_state()
    state[task_name] = {
        "last_run": datetime.now().isoformat(),
        "success": success,
        "output": output
    }
    with open(STATE_FILE_MAINT, "w") as f:
        json.dump(state, f, indent=2)

def run_task(task: str):
    """Run a single maintenance task using maintenance.py"""
    cmd = [str(VENV_PYTHON), str(MAINT_SCRIPT), "--task", task, "--config", str(CONFIG_FILE)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stdout.strip() + ("\n" + result.stderr.strip() if result.stderr else "")
        success = result.returncode == 0
        log_file = log_task(task, output)
        save_maint_state(task, success, output)
        return success, output, log_file
    except Exception as e:
        log_file = log_task(task, str(e))
        save_maint_state(task, False, str(e))
        return False, str(e), log_file

# -------------------------
# ---------- Telegram Handlers ----------
# Monitor Handlers
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    success = await run_live_check()
    if not success:
        await update.message.reply_text("⚠️ Failed to perform live check. Using last saved metrics.")
    state = load_monitor_state()
    if not state:
        await update.message.reply_text("No monitor state available yet.")
        return
    await update.message.reply_text(format_metrics(state))

async def monitor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await status_command(update, context)

# Maintenance Handlers
async def maintenance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("All Tasks", callback_data="all")],
        [InlineKeyboardButton("OS Updates", callback_data="os_update")],
        [InlineKeyboardButton("Gravity Update", callback_data="gravity")],
        [InlineKeyboardButton("Pi-hole Update", callback_data="pihole_update")],
        [InlineKeyboardButton("Clear Logs", callback_data="clear_logs")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Choose a maintenance task:", reply_markup=reply_markup)

async def maintenance_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_maint_state()
    if not state:
        await update.message.reply_text("No maintenance history found.")
        return
    lines = []
    for task, info in state.items():
        last_run = info.get("last_run", "Never")
        status = "✅ Success" if info.get("success") else "❌ Failed"
        lines.append(f"{task}: {status} (Last run: {last_run})")
    await update.message.reply_text("\n".join(lines))

async def maintenance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    task = query.data
    await query.answer()
    await query.edit_message_text(text=f"Running {task}...")

    if task == "all":
        results = []
        for t in ["os_update", "gravity", "pihole_update", "clear_logs"]:
            success, output, log_file = run_task(t)
            results.append((t, success, log_file))
        summary = [f"{t}: {'✅' if s else '❌'} (Log: {lf.name})" for t, s, lf in results]
        await context.bot.send_message(chat_id=query.message.chat.id,
                                       text="All tasks completed:\n" + "\n".join(summary))
    else:
        success, output, log_file = run_task(task)
        truncated_output = (output[:4000] + '...') if len(output) > 4000 else output
        await context.bot.send_message(chat_id=query.message.chat.id,
                                       text=f"{task}: {'✅' if success else '❌'}\n"
                                            f"Log: {log_file.name}\nOutput:\n{truncated_output}")

# -------------------------
# ---------- Main Bot Setup ----------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Monitor commands
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("monitor", monitor_command))

    # Maintenance commands
    app.add_handler(CommandHandler(["maintenance", "maintain"], maintenance_command))
    app.add_handler(CommandHandler("maintenance_status", maintenance_status))
    app.add_handler(CallbackQueryHandler(
        maintenance_callback,
        pattern="^(all|os_update|gravity|pihole_update|clear_logs)$"
    ))

    print("Merged Monitor + Maintenance Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
