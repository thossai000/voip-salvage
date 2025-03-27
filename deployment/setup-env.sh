#!/bin/bash
# setup-env.sh - Create virtual environment and install dependencies

set -e

# Determine script directory regardless of where it's called from
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Setting up environment for Jitsi Meet VoIP Benchmarking Tool..."

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv .venv || {
    echo "Error: Failed to create virtual environment. Please ensure python3-venv is installed."
    echo "On Debian/Ubuntu: sudo apt-get install python3-venv"
    exit 1
}

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate || {
    echo "Error: Failed to activate virtual environment."
    exit 1
}

# Install dependencies
echo "Installing dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt || {
        echo "Error: Failed to install dependencies from requirements.txt."
        echo "Please check the error message above and make sure you have internet access."
        exit 1
    }
else
    echo "Warning: requirements.txt not found. Installing minimal dependencies."
    pip install pytest opuslib wave numpy || {
        echo "Error: Failed to install minimal dependencies."
        exit 1
    }
fi

# Install system dependencies
echo "Checking for system dependencies..."
if command -v apt-get &> /dev/null; then
    echo "Debian/Ubuntu system detected."
    echo "To install system dependencies, run:"
    echo "sudo apt-get install libopus0 libopus-dev ffmpeg"
elif command -v yum &> /dev/null; then
    echo "RHEL/CentOS system detected."
    echo "To install system dependencies, run:"
    echo "sudo yum install opus opus-devel ffmpeg"
elif command -v pacman &> /dev/null; then
    echo "Arch Linux system detected."
    echo "To install system dependencies, run:"
    echo "sudo pacman -S opus ffmpeg"
else
    echo "Unknown system. Please manually install libopus and ffmpeg."
fi

# Ensure directories exist and make scripts executable
echo "Making scripts executable..."
for dir in "voip_benchmark" "tests"; do
    if [ -d "$dir" ]; then
        find "$dir" -name "*.py" -exec chmod +x {} \;
    else
        echo "Warning: Directory '$dir' not found. Skipping making scripts executable."
    fi
done

# Create empty results directory if it doesn't exist
mkdir -p results

echo "Setup complete!"
echo "To activate the environment, run: source .venv/bin/activate"