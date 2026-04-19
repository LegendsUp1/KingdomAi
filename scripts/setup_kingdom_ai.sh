#!/bin/bash

# Kingdom AI Setup Script
# This script sets up the Kingdom AI environment

set -e  # Exit on error

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Setting up Kingdom AI ===${NC}"

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Set up configuration
echo "Setting up configuration..."
mkdir -p config
if [ ! -f "config/config.json" ]; then
    cp config.json.template config/config.json
fi

# Set up logging
echo "Setting up logging..."
mkdir -p logs

# Set file permissions
echo "Setting file permissions..."
chmod +x scripts/*.sh
find . -type d -exec chmod 755 {} \;
find . -type f -exec chmod 644 {} \;
chmod +x scripts/*.sh  # Make sure scripts stay executable

echo -e "${GREEN}=== Kingdom AI setup complete! ===${NC}"
echo "You can now run Kingdom AI using: ./scripts/launch_kingdom_ai.sh"
