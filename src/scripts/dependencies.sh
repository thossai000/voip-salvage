#!/bin/bash
# dependencies.sh - Check dependencies for VoIP benchmarking

# Returns 0 if all required dependencies are present, 1 otherwise

check_dependencies() {
  local MISSING_DEPS=()

  # Check for Docker
  if ! command -v docker &> /dev/null; then
    MISSING_DEPS+=("Docker")
  fi

  # Check for Docker Compose
  if ! command -v docker-compose &> /dev/null; then
    MISSING_DEPS+=("Docker Compose")
  fi

  # Check for Python
  if ! command -v python3 &> /dev/null; then
    MISSING_DEPS+=("Python 3")
  fi

  # Check for FFmpeg
  if ! command -v ffmpeg &> /dev/null; then
    MISSING_DEPS+=("FFmpeg")
  fi

  # Check for tshark (optional)
  if ! command -v tshark &> /dev/null; then
    echo "Notice: tshark is not installed. Packet capture tests will be skipped."
  fi

  # Report missing dependencies
  if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo "The following dependencies are missing:"
    for dep in "${MISSING_DEPS[@]}"; do
      echo "  - $dep"
    done
    echo ""
    echo "Please install the missing dependencies and run this script again."
    
    # Provide installation instructions
    echo ""
    echo "Installation instructions:"
    
    # Docker installation instructions if missing
    if [[ " ${MISSING_DEPS[@]} " =~ " Docker " ]]; then
      echo "  Docker: sudo apt install docker.io"
      echo "          sudo usermod -aG docker $USER"
    fi
    
    # Docker Compose installation instructions if missing
    if [[ " ${MISSING_DEPS[@]} " =~ " Docker Compose " ]]; then
      echo "  Docker Compose: sudo apt install docker-compose"
    fi
    
    # Python installation instructions if missing
    if [[ " ${MISSING_DEPS[@]} " =~ " Python 3 " ]]; then
      echo "  Python 3: sudo apt install python3 python3-pip"
    fi
    
    # FFmpeg installation instructions if missing
    if [[ " ${MISSING_DEPS[@]} " =~ " FFmpeg " ]]; then
      echo "  FFmpeg: sudo apt install ffmpeg"
    fi
    
    echo ""
    echo "Note: You may need to log out and back in for group changes to take effect."
    
    return 1
  fi
  
  return 0
} 