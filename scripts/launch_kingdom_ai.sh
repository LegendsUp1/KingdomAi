#!/bin/bash
# Kingdom AI Launch Script for Linux
# Description: Launches the Kingdom AI system with proper error handling and logging

set -e  # Exit on error

# Script variables
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_PATH="python3"
VENV_PATH="${PROJECT_ROOT}/venv"
REQUIREMENTS_FILE="${PROJECT_ROOT}/requirements.txt"
MAIN_SCRIPT="${PROJECT_ROOT}/main.py"
VALIDATE_SCRIPT="${PROJECT_ROOT}/scripts/validate_launch.py"
LOG_DIR="${PROJECT_ROOT}/logs"
LOG_FILE="${LOG_DIR}/kingdom_ai_$(date +%Y%m%d_%H%M%S).log"
ENV_FILE="${PROJECT_ROOT}/.env"
CONFIG_DIR="${PROJECT_ROOT}/config"
CONFIG_FILE="${CONFIG_DIR}/config.json"

# Logging function
log() {
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "$timestamp - $1"
    mkdir -p "$LOG_DIR"
    echo "$timestamp - $1" >> "$LOG_FILE"
}

# Main execution
log "=== Kingdom AI Launch Script ==="

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

log "Running system checks..."

# Activate virtual environment
source "${VENV_PATH}/bin/activate"

# Run validation script
log "Running pre-launch validation..."
python "$VALIDATE_SCRIPT"
if [ $? -ne 0 ]; then
    log "Pre-launch validation failed"
    exit 1
fi

# Start Kingdom AI
log "All checks passed. Starting Kingdom AI..."

# Set environment variables
export PYTHONPATH="$PROJECT_ROOT"
export KINGDOM_ROOT="$PROJECT_ROOT"

# Start the main script
log "Starting Kingdom AI..."
exec python "$MAIN_SCRIPT" >> "$LOG_FILE" 2>&1
