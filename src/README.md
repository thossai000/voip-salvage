# Jitsi Meet VoIP Benchmarking Tool

A solution for measuring VoIP audio transmission metrics in Jitsi Meet environments.

## Overview

The Jitsi Meet VoIP Benchmarking Tool provides an accurate way to evaluate audio transmission between Docker containers using RTP (Real-time Transport Protocol). The tool generates deterministic audio samples, transmits them through proper RTP packets between containers, captures the network traffic, and analyzes the results to provide   performance metrics.

## Latest Benchmark Results

The most recent benchmark demonstrated successful audio transmission with the following metrics:

- **RTP packets transmitted**: 1500 packets
- **Total RTP bytes transmitted**: 564,000 bytes
- **Original WAV file size**: 480,078 bytes
- **Transmission ratio**: 117%
- **Additional overhead**: 17% (due to RTP headers)

These results confirm that the RTP-based approach correctly simulates and measures VoIP traffic with proper packet headers and timing, making it suitable for accurate comparison with other data transmission methods.

## Key Features

- **RTP Audio Transmission**: Generates properly formatted RTP packets with correct headers and timing
- **Deterministic WAV File Generation**: Creates test audio files with configurable parameters
- **Traffic Analysis**: Captures and analyzes network traffic with tshark/Wireshark
- **  Metrics**: Reports on packet counts, bytes transmitted, transmission ratios, and more
- **VoIP-Optimized Format**: Converts standard WAV files to VoIP-friendly format (8000Hz, mono, PCM_S16LE)
- **Docker Integration**: Works with Jitsi Meet Docker containers (web, prosody, jicofo, jvb)
- **Direct Container Communication**: No browser dependencies for more reliable, consistent results

## System Requirements

### Hardware Requirements
- **CPU**: 2+ cores recommended
- **RAM**: 4GB+ recommended
- **Storage**: 1GB free space for installation and results
- **Network**: Internet connection for Docker image downloads

### Software Requirements
- **Operating System**: Linux (Ubuntu 20.04+ recommended)
- **Docker**: Version 19.03+ for container management
- **Docker Compose**: Version 1.25+ for multi-container orchestration
- **Python**: Version 3.6+ for benchmark scripts
- **tshark/Wireshark**: For packet capture and analysis
- **ffmpeg**: For audio file generation and conversion
- **bc**: For command-line calculations

## Installation

### Automatic Setup

The easiest way to set up the environment is to use the provided setup script:

```bash
# Make the script executable if needed
chmod +x scripts/setup.sh

# Run the setup script
./scripts/setup.sh
```

The setup script will:
1. Check for required dependencies
2. Create necessary directories
3. Generate a default test audio file
4. Pull required Docker images
5. Install Python dependencies

### Manual Installation

If you prefer to set up manually, follow these steps:

#### 1. Install System Dependencies

```bash
# Debian/Ubuntu
sudo apt-get update
sudo apt-get install -y docker.io docker-compose ffmpeg tshark python3 python3-pip bc

# RHEL/CentOS/Fedora
sudo dnf install -y docker docker-compose ffmpeg wireshark python3 python3-pip bc

# Arch Linux
sudo pacman -Sy --noconfirm docker docker-compose ffmpeg wireshark-cli python python-pip bc
```

#### 2. Set Up User Permissions

```bash
# Add current user to Docker group (avoids needing sudo for Docker commands)
sudo usermod -aG docker $USER

# Add current user to Wireshark group (allows packet capture without sudo)
sudo usermod -aG wireshark $USER

# Log out and log back in for the changes to take effect
```

#### 3. Install Python Dependencies

```bash
# Install required Python packages
pip install pyshark requests wave numpy
```

#### 4. Start Docker Service

```bash
# Start Docker service
sudo systemctl start docker

# Enable Docker to start at boot
sudo systemctl enable docker

# Verify Docker is running
docker info
```

#### 5. Create Required Directories

```bash
mkdir -p audio config/{web,prosody} results
```

#### 6. Pull Docker Images

```bash
cd docker
docker-compose pull
cd ..
```

## Quick Start

### Complete Benchmark Workflow

For a complete end-to-end benchmark, follow these steps:

```bash
# 1. Set up the environment (if not already done)
./scripts/setup.sh

# 2. Create a VoIP-optimized audio file
./scripts/create_wav.sh --duration 30 --frequency 440 --sample-rate 8000 --output audio/voip_ready.wav

# 3. Run the benchmark
./scripts/rtp/rtp_benchmark.sh
```

### Step-by-Step Benchmark Process

If you prefer more control over the process:

#### 1. Create a Test WAV File

Generate a custom WAV file for testing:

```bash
./scripts/create_wav.sh --duration 30 --frequency 440 --channels 1 --output audio/test_audio.wav
```

#### 2. Convert to VoIP Format

Prepare the WAV file for optimal RTP transmission:

```bash
ffmpeg -i audio/test_audio.wav -ar 8000 -ac 1 -acodec pcm_s16le audio/voip_ready.wav
```

#### 3. Run the RTP Benchmark

```bash
./scripts/rtp/rtp_benchmark.sh
```

The script automatically:
1. Checks for all required dependencies
2. Validates the VoIP-ready WAV file
3. Identifies the Jitsi Meet JVB container
4. Starts packet capture with tshark
5. Launches the RTP receiver
6. Transmits RTP packets from the source WAV file
7. Analyzes the results and generates a report

### 4. View Results

Results are stored in a timestamped directory under `/tmp/jitsi-results-*/` and include:
- Benchmark results summary
-   traffic statistics
- RTP stream analysis
- Packet capture files

**Note**: The benchmark script automatically cleans up old result directories before creating a new one, ensuring that only the most recent results are kept.

## Configuration

### Docker Compose Configuration

The Docker Compose file includes resource limits to prevent container overutilization:

- **Web container**: 0.5 CPU, 512MB RAM
- **Prosody container**: 0.3 CPU, 256MB RAM
- **Jicofo container**: 0.3 CPU, 256MB RAM
- **JVB container**: 1.0 CPU, 1GB RAM

You can adjust these limits in `docker/docker-compose.yml` based on your system capabilities.

### Docker Networking

The benchmarking tool requires proper network connectivity between containers. The default Docker bridge network is used, but you can customize it if needed:

```bash
# Create a custom Docker network (optional)
docker network create jitsi-network

# Edit docker-compose.yml to use the custom network if desired
# Open docker/docker-compose.yml and modify the networks section
```

### Audio Configuration

You can configure the audio test files used for benchmarking:

- **Sample Rate**: Default VoIP-optimized format is 8000 Hz
- **Audio Channels**: Mono (1 channel) recommended for VoIP
- **Duration**: Default 30 seconds, can be adjusted
- **Frequency**: Default 440 Hz (A4 note)

To modify these settings when creating test files:

```bash
# Create a custom WAV file with different parameters
./scripts/create_wav.sh --duration 60 --frequency 880 --channels 1 --output audio/custom_test.wav
```

### RTP Configuration

RTP transmission parameters can be customized in the `scripts/rtp/rtp_send.py` script:

- **Packet Size**: Default is 160 bytes per packet
- **Sample Rate**: Default 8000 Hz
- **Payload Type**: Default 0 (PCM u-law)
- **SSRC**: Random by default

### Path Handling

All scripts in this project use relative paths to ensure portability:

- Scripts use `SCRIPT_DIR=$(dirname "${BASH_SOURCE[0]}")` to determine their location
- Paths are constructed relative to the script or repository root
- No hardcoded absolute paths are used
- The `.venv` directory is excluded from version control via `.gitignore`

This approach ensures the benchmarking tool can be deployed to any environment without modifications.

### Packet Capture Configuration

Packet capture settings can be adjusted in `scripts/rtp/rtp_benchmark.sh`:

- **Capture Interface**: Default `any`
- **Capture Filter**: Default `udp port 10000`
- **Capture Format**: Default PCAPNG
- **Capture Duration**: Matches audio duration + buffer time

## Metrics and Analysis

### General Metrics
- Total packets and bytes transmitted
- Test duration and average bitrate
- Packets per second

### RTP-Specific Metrics
- RTP packet count and total bytes
- Transmission ratio (compared to original WAV file)
- RTP stream information and packet loss statistics

### Interpreting Results

A successful test should show:
1. A significant number of RTP packets (typically 1000+ for a 30s file)
2. Total bytes transmitted exceeding the original WAV file size (due to RTP headers)
3. A transmission ratio over 100% (due to added headers)

## Advanced Usage

### Running Individual Components

**RTP Receiver**:
```bash
python3 scripts/rtp/rtp_receive.py --port 10000 --output output.wav --duration 30 --debug
```

**RTP Sender**:
```bash
python3 scripts/rtp/rtp_send.py audio/voip_ready.wav --dest-ip 172.17.0.3 --dest-port 10000 --debug
```

### Custom Packet Capture

For more   packet analysis:
```bash
tshark -i any -f "udp port 10000" -w capture.pcapng
```

## Directory Structure

After installation, the directory structure will look like this:

```
jitsi-meet-benchmark/
├── audio/                # Directory for test audio files
│   └── test_audio_30s.wav  # Default test audio file
├── config/               # Configuration files for Jitsi Meet
├── docker/               # Docker-related files
│   └── docker-compose.yml  # Container configuration
├── results/              # Directory for benchmark results
├── scripts/              # Benchmarking and utility scripts
│   ├── create_wav.sh       # Script to create test WAV files
│   ├── setup.sh            # Setup script for environment preparation
│   ├── dependencies.sh     # Dependency checking script
│   └── rtp/                # RTP-specific scripts
│       ├── rtp_benchmark.sh  # Main RTP benchmark script
│       ├── rtp_receive.py    # RTP receiver script
│       └── rtp_send.py       # RTP sender script
└── README.md             # Main documentation
```

## Troubleshooting

### Permission Issues

If you encounter permission issues with Docker or packet capture:

```bash
# Verify group membership
groups

# If you don't see docker or wireshark in the output, you may need to log out and log back in
# or restart your system after adding yourself to these groups
```

### Network Issues

If containers cannot communicate:

```bash
# Check Docker network configuration
docker network ls
docker network inspect bridge

# Verify container IP addresses
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' jvb
```

### Missing Dependencies

If scripts fail due to missing dependencies:

```bash
# Verify all required tools are installed
command -v docker docker-compose python3 ffmpeg tshark bc

# If any command returns empty, install the corresponding package
```

### Other Common Issues

- **No RTP packets captured**: Verify JVB container is running and accessible; check firewall settings
- **Audio transfer failure**: Confirm receiver is running on correct port; check for network packet loss
- **Script execution errors**: Ensure Python dependencies and system tools are properly installed
- **WAV format issues**: Verify WAV file is properly converted to VoIP format (8000Hz, mono, PCM_S16LE)

## Deploying on a Different VM

When using this project on a different VM or system, follow these steps to avoid path-related issues:

1. **Create a new virtual environment** instead of using the included `.venv` directory:
   ```bash
   # Remove the existing .venv directory
   rm -rf .venv
   
   # Create a fresh virtual environment
   python3 -m venv .venv
   
   # Activate the virtual environment
   source .venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   ```

2. **Use relative paths in scripts**:
   The scripts have been designed to use relative paths where possible, but some commands may need adjustment for your specific environment.

3. **Review the `docker-compose.yml` file**:
   Make sure the volume mappings use relative paths that work with your directory structure.

4. **Check for absolute paths in configuration files**:
   If you encounter any issues related to hardcoded paths, check configuration files in the `config` directory.