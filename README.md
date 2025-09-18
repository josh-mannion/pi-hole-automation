Overview
--------
The Pi-hole Automation Suite provides:

Down Alert Module: Monitors Pi-hole and internet connectivity, sending Telegram alerts on status changes.

Maintenance Module: Performs OS updates, Pi-hole updates, Gravity updates, log cleanup, and reports results via Telegram.

Monitor Module: Tracks CPU, RAM, disk usage, and system temperature, alerting via Telegram when thresholds are exceeded.

Telegram Bot Integration: Allows control and status checks remotely. The setup script automatically detects your chat ID after you send a message to the bot.

Automated Scheduling: Cron jobs ensure modules run regularly without user intervention.

Note: Telegram bot is optional.

Directory Structure
-------------------
```text
pi-hole-automation/
├── README.md                 # Project overview and instructions
├── setup/                    # Setup and installation scripts
│   ├── config.json           # Stores Telegram token, chat ID, paths, and settings
│   ├── initial_setup.sh      # Sets up environment, dependencies, and Telegram integration
│   ├── install_all.sh        # Installs all modules
│   ├── requirements.txt      # Python dependencies
│   └── setup.log
├── down_alert/               # Down Alert Module
│   ├── logs/
│   ├── scripts/
│   │   ├── down_alert.py
│   │   └── run_down_alert.sh
│   └── state/
├── maintenance/              # Maintenance Module
│   ├── logs/
│   ├── scripts/
│   │   ├── maintenance.py
│   │   ├── maintenance_bot.py
│   │   └── run_maintenance.sh
│   └── state/
├── monitor/                  # Monitor Module
│   ├── logs/
│   ├── scripts/
│   │   ├── monitor.py
│   │   ├── monitor_bot.py
│   │   └── run_monitor.sh
│   └── state/
└── venv/                     # Python virtual environment (created during setup)



Install & Setup
---------------

git clone <repo_url>

cd pi-hole-automation

cd setup

bash initial_setup.sh



