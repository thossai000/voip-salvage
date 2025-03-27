# VoIP System User Guide

This guide explains how to use our VoIP audio testing tool.

## Table of Contents

1. [What This Tool Does](#what-this-tool-does)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Step-by-Step Test](#step-by-step-test)
5. [Understanding Your Results](#understanding-your-results)
6. [Advanced Options](#advanced-options)
7. [Troubleshooting](#troubleshooting)

## What This Tool Does

This tool lets you:
- Send audio files between containers using RTP
- Measure how much data gets transmitted
- Test VoIP audio transmission with the Opus codec

## Installation

### Prerequisites

You'll need:
- Docker and Docker Compose installed
- Python 3.6 or higher
- System packages:
  ```bash
  # Ubuntu/Debian
  sudo apt install libopus0 libopus-dev ffmpeg tshark
  ```

### Setup

Run the setup script to check dependencies and prepare the environment:

```bash
./scripts/setup.sh
```

The script checks for dependencies but doesn't install them automatically. If missing anything, you'll need to install it manually.

## Quick Start

Here's how to run a basic VoIP test:

```bash
# 1. Make sure you're in the project root directory

# 2. Create a test WAV file (if you don't have one)
./scripts/create_wav.sh --output audio/test_audio_30s.wav

# 3. Convert to VoIP format
ffmpeg -i audio/test_audio_30s.wav -ar 8000 -ac 1 -acodec pcm_s16le audio/voip_ready.wav

# 4. Start Docker containers
cd docker
docker-compose up -d
cd ..

# 5. Run the benchmark
./scripts/rtp/rtp_benchmark.sh --file audio/voip_ready.wav --codec opus --bitrate 24000
```

This sends the audio file using RTP and shows you statistics about the transmission.

## Step-by-Step Test

Let's break down the process in more detail:

1. **Create a test WAV file**:
   ```bash
   ./scripts/create_wav.sh --output audio/test_audio_30s.wav --duration 30
   ```
   
   This creates a 30-second WAV file with a test tone.

2. **Convert to VoIP format**:
   ```bash
   ffmpeg -i audio/test_audio_30s.wav -ar 8000 -ac 1 -acodec pcm_s16le audio/voip_ready.wav
   ```
   
   VoIP systems typically use 8kHz mono audio for efficiency.

3. **Start Docker containers**:
   ```bash
   cd docker
   docker-compose up -d
   cd ..
   ```
   
   Check they're running with:
   ```bash
   docker ps
   ```
   
   You should see these containers running:
   - `web`: Web interface
   - `prosody`: Messaging server
   - `jicofo`: Connection manager
   - `jvb`: Video bridge for media

4. **Run the benchmark**:
   ```bash
   ./scripts/rtp/rtp_benchmark.sh --file audio/voip_ready.wav --codec opus --bitrate 24000
   ```
   
   This script:
   - Starts a receiver process
   - Sends the audio file
   - Captures transmission statistics
   - Saves the received audio

5. **Check the results**:
   
   Results are saved in the `results` directory with:
   - Received audio file
   - Sender log
   - Receiver log
   - CSV file with metrics

## Understanding Your Results

After running the test, you'll see output like this:

```
Results:
  Packets Sent: 1500
  Bytes Sent: 498000
  Packets Received: 1499
  Bytes Received: 497670
  Missing Packets: 1
  Packet Loss: 0.07%
  Compression Ratio: 3.8%
```

Key metrics:
- **Packets Sent/Received**: Number of RTP packets transmitted
- **Bytes Sent/Received**: Total data volume
- **Missing Packets**: Packets that didn't arrive
- **Packet Loss**: Percentage of packets lost during transmission
- **Compression Ratio**: How much smaller the audio is compared to the original 
  - With Opus codec, you'll see 3-10% (90-97% size reduction)
  - Without codec, you'll see 117% (17% larger due to RTP headers)

## Advanced Options

### Testing with Different Codecs

Try different codecs and bitrates:

```bash
# No codec (PCM audio)
./scripts/rtp/rtp_benchmark.sh --file audio/voip_ready.wav --codec none

# Opus at low bitrate (8 kbps)
./scripts/rtp/rtp_benchmark.sh --file audio/voip_ready.wav --codec opus --bitrate 8000

# Opus at high bitrate (64 kbps)
./scripts/rtp/rtp_benchmark.sh --file audio/voip_ready.wav --codec opus --bitrate 64000
```

### Changing Test Duration

Control how long the test runs:

```bash
./scripts/rtp/rtp_benchmark.sh --file audio/voip_ready.wav --duration 5
```

### Debugging

Enable debug output:

```bash
./scripts/rtp/rtp_benchmark.sh --file audio/voip_ready.wav --codec opus --debug
```

## Troubleshooting

### Common Issues

#### Docker Containers Not Starting

**Problem**: Docker containers won't start

**Solution**: 
```bash
# Check Docker is running
docker info

# Try restarting Docker
sudo systemctl restart docker

# Try again
cd docker
docker-compose up -d
```

#### WAV File Issues

**Problem**: "WAV file not found" or "Error opening WAV file"

**Solution**: Check the path and make sure the file exists:

```bash
# Create a test file if needed
./scripts/create_wav.sh --output audio/test_audio_30s.wav

# Convert to VoIP format
ffmpeg -i audio/test_audio_30s.wav -ar 8000 -ac 1 -acodec pcm_s16le audio/voip_ready.wav

# Verify the file exists
ls -l audio/voip_ready.wav
```

#### Benchmark Script Errors

**Problem**: The benchmark script fails with errors

**Solution**:
1. Make sure the script is executable:
   ```bash
   chmod +x scripts/rtp/rtp_benchmark.sh
   ```

2. Check if the receiver is already running:
   ```bash
   ps aux | grep rtp_receive.py
   # Kill any hanging processes if needed
   kill <PID>
   ```

3. Try with debug output:
   ```bash
   ./scripts/rtp/rtp_benchmark.sh --file audio/voip_ready.wav --codec opus --debug
   ``` 