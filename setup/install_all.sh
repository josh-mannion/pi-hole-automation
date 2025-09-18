#!/bin/bash

# ----------------------------------------
# Install All Modules for Pi-hole Automation
# ----------------------------------------

set -euo pipefail

# -------------------------
# Determine Base Directory and Config
# -------------------------
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="$BASE_DIR/setup/config.json"
VENV_DIR=$(jq -r '.paths.venv_dir' "$CONFIG_FILE")
PYTHON="$BASE_DIR/$VENV_DIR/bin/python3"

# -------------------------
# Activate virtual environment
# -------------------------
if [ ! -d "$BASE_DIR/$VENV_DIR" ]; then
    echo "Virtual environment not found at $VENV_DIR."
    echo "Please run initial_setup.sh first."
    exit 1
fi

# shellcheck disable=SC1090
source "$BASE_DIR/$VENV_DIR/bin/activate"

# -------------------------
# Install Python packages
# -------------------------
REQUIREMENTS_FILE=$(jq -r '.paths.requirements_file' "$CONFIG_FILE")
if [ -f "$BASE_DIR/$REQUIREMENTS_FILE" ]; then
    echo "Installing Python packages from requirements.txt..."
    "$PYTHON" -m pip install --upgrade pip
    "$PYTHON" -m pip install -r "$BASE_DIR/$REQUIREMENTS_FILE"
else
    echo "No requirements.txt found in setup/. Skipping Python package installation."
fi

# -------------------------
# Function to run a module using paths from config
# -------------------------
run_module() {
    local MODULE_NAME=$1

    local SCRIPT=$(jq -r ".paths.$MODULE_NAME.script" "$CONFIG_FILE")
    local LOG_DIR=$(jq -r ".paths.$MODULE_NAME.logs" "$CONFIG_FILE")
    local LOG_FILE="$BASE_DIR/$LOG_DIR/$(date +%Y%m%d_%H%M%S).log"

    if [ ! -f "$BASE_DIR/$SCRIPT" ]; then
        echo "[ERROR] Script not found: $BASE_DIR/$SCRIPT"
        return 1
    fi

    echo "Running $MODULE_NAME..."
    mkdir -p "$BASE_DIR/$LOG_DIR"

    # Run Python script via venv and pass config
    if "$PYTHON" "$BASE_DIR/$SCRIPT" --config "$CONFIG_FILE" &> "$LOG_FILE"; then
        echo "$MODULE_NAME completed successfully. Log: $LOG_FILE"
        return 0
    else
        echo "[ERROR] $MODULE_NAME failed. Check log: $LOG_FILE"
        return 1
    fi
}

# -------------------------
# Run all modules
# -------------------------
MODULES=("down_alert" "maintenance" "monitor")
FAILED_MODULES=()

for MODULE in "${MODULES[@]}"; do
    if ! run_module "$MODULE"; then
        FAILED_MODULES+=("$MODULE")
    fi
done

# -------------------------
# Report results
# -------------------------
if [ "${#FAILED_MODULES[@]}" -gt 0 ]; then
    echo
    echo "The following modules failed:"
    for m in "${FAILED_MODULES[@]}"; do
        echo " - $m"
    done
    echo
else
    echo "All modules installed and ran successfully!"
fi
