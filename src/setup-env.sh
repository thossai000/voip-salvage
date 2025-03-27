#!/bin/bash
# setup-env.sh - Create virtual environment and install dependencies

set -e

echo "Setting up environment for Jitsi Meet VoIP Benchmarking Tool..."

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv .venv

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    pip install pyshark requests
fi

echo "Making scripts executable..."
chmod +x scripts/*.sh
chmod +x scripts/rtp/*.sh
chmod +x scripts/rtp/*.py

echo "Setup complete!"
echo "To activate the environment, run: source .venv/bin/activate"
