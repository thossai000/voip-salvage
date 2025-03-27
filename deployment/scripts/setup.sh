#!/bin/bash
# setup.sh - Set up environment for VoIP benchmarking

set -e

# Source the dependencies script
SCRIPT_DIR="$(dirname "$0")"
REPO_ROOT="$(realpath "$SCRIPT_DIR/..")"
source "${SCRIPT_DIR}/dependencies.sh"

show_help() {
  echo "Usage: $0 [OPTIONS]"
  echo "Set up environment for VoIP benchmarking."
  echo ""
  echo "Options:"
  echo "  --skip-docker         Skip Docker setup"
  echo "  --skip-python         Skip Python setup"
  echo "  --help                Show this help message"
}

# Default values
SETUP_DOCKER=true
SETUP_PYTHON=true

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-docker)
      SETUP_DOCKER=false
      shift
      ;;
    --skip-python)
      SETUP_PYTHON=false
      shift
      ;;
    --help)
      show_help
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      show_help
      exit 1
      ;;
  esac
done

echo "Setting up VoIP benchmarking environment..."

# Check dependencies
echo "Checking dependencies..."
if ! check_dependencies; then
  exit 1
fi

# Create directories
echo "Creating directories..."
mkdir -p "${REPO_ROOT}/audio"
mkdir -p "${REPO_ROOT}/config/web"
mkdir -p "${REPO_ROOT}/config/prosody"
mkdir -p "${REPO_ROOT}/results"

# Create default test audio file if it doesn't exist
echo "Creating default test audio file..."
if [ ! -f "${REPO_ROOT}/audio/test_audio_30s.wav" ]; then
  "${SCRIPT_DIR}/create_wav.sh" --duration 30 --frequency 440 --output "${REPO_ROOT}/audio/test_audio_30s.wav"
fi

# Set up Docker if requested
if [ "$SETUP_DOCKER" = true ]; then
  echo "Setting up Docker containers..."
  
  # Ensure Docker is running
  if ! docker info &> /dev/null; then
    echo "Docker is not running. Please start Docker and try again."
    exit 1
  fi
  
  # Pull required images
  echo "Pulling Jitsi Meet Docker images..."
  cd "${REPO_ROOT}/docker"
  docker-compose pull
  cd - > /dev/null
fi

# Set up Python environment if requested
if [ "$SETUP_PYTHON" = true ]; then
  echo "Setting up Python environment..."
  
  # Install dependencies
  pip install pyshark requests
fi

echo "Setup completed successfully."
echo ""
echo "Next steps:"
echo "  1. Generate a test WAV file: ${SCRIPT_DIR}/create_wav.sh --output audio/test_audio.wav"
echo "  2. Convert to VoIP format: ffmpeg -i audio/test_audio.wav -ar 8000 -ac 1 -acodec pcm_s16le audio/voip_ready.wav"
echo "  3. Run a benchmark: ${SCRIPT_DIR}/rtp/rtp_benchmark.sh"
echo ""
echo "For more information, see ${REPO_ROOT}/README.md"

exit 0