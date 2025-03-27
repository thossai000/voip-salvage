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

Activate the virtual environment and install required dependencies:

```bash
# Option 1: Use the included virtual environment
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows

# Option 2: Install dependencies directly
pip install -r requirements.txt
```

## Quick Start

Here's how to run a basic VoIP test:

```bash
# 1. Make sure you're in the project root directory

# 2. Create a test WAV file (if you don't have one)
python -c "import wave, numpy as np, struct; w = wave.open('audio/test_audio_30s.wav', 'w'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); data = np.sin(2 * np.pi * 440 * np.arange(0, 30, 1/48000)).astype(np.float32); w.writeframes(struct.pack('<%dh' % len(data), *(np.int16(data * 32767)))); w.close(); print('Created test audio file: audio/test_audio_30s.wav')"

# 3. Convert to VoIP format
ffmpeg -i audio/test_audio_30s.wav -ar 8000 -ac 1 -acodec pcm_s16le audio/voip_ready.wav

# 4. Start Docker containers
cd docker
docker-compose up -d
cd ..

# 5. Run the benchmark
python -c "from voip_benchmark.rtp.simulator import simulate_rtp_transmission; success = simulate_rtp_transmission('audio/voip_ready.wav', 'results/output.wav', codec='opus', bitrate=24000); print(f'Benchmark completed: {success}')"
```

This sends the audio file using RTP and shows you statistics about the transmission.

## Step-by-Step Test

Let's break down the process in more detail:

1. **Create a test WAV file**:
   ```bash
   python -c "import wave, numpy as np, struct; w = wave.open('audio/test_audio_30s.wav', 'w'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); data = np.sin(2 * np.pi * 440 * np.arange(0, 30, 1/48000)).astype(np.float32); w.writeframes(struct.pack('<%dh' % len(data), *(np.int16(data * 32767)))); w.close(); print('Created test audio file: audio/test_audio_30s.wav')"
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
   # Start receiver in background
   python -c "from voip_benchmark.rtp.receiver import receive_rtp_stream; import threading; thread = threading.Thread(target=receive_rtp_stream, args=(5004, 'results/received.wav', 10.0, 'opus', 24000)); thread.daemon = True; thread.start(); print('Receiver started, listening on port 5004...')"
   
   # Send audio
   python -c "from voip_benchmark.rtp.sender import send_rtp_stream; success, bytes_sent, packets_sent = send_rtp_stream('audio/voip_ready.wav', '127.0.0.1', 5004, codec='opus', bitrate=24000); print(f'Sent {packets_sent} packets ({bytes_sent} bytes)')"
   ```
   
   This:
   - Starts a receiver process
   - Sends the audio file
   - Captures transmission statistics
   - Saves the received audio

5. **Check the results**:
   
   Results are saved in the `results` directory with the received audio file.

## Understanding Your Results

After running the test, you'll see output like this:

```
Sent 1500 packets (498000 bytes)
Receiver: Received 1499 packets (497670 bytes)
Missing packets: 1
Packet loss: 0.07%
Compression ratio: 3.8%
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
python -c "from voip_benchmark.rtp.simulator import simulate_rtp_transmission; success = simulate_rtp_transmission('audio/voip_ready.wav', 'results/output_none.wav', codec='none'); print(f'Benchmark completed: {success}')"

# Opus at low bitrate (8 kbps)
python -c "from voip_benchmark.rtp.simulator import simulate_rtp_transmission; success = simulate_rtp_transmission('audio/voip_ready.wav', 'results/output_8k.wav', codec='opus', bitrate=8000); print(f'Benchmark completed: {success}')"

# Opus at high bitrate (64 kbps)
python -c "from voip_benchmark.rtp.simulator import simulate_rtp_transmission; success = simulate_rtp_transmission('audio/voip_ready.wav', 'results/output_64k.wav', codec='opus', bitrate=64000); print(f'Benchmark completed: {success}')"
```

### Testing with Network Conditions

Simulate different network conditions:

```bash
# Test with packet loss and jitter
python -c "from voip_benchmark.rtp.simulator import simulate_rtp_transmission; success = simulate_rtp_transmission('audio/voip_ready.wav', 'results/output_network.wav', codec='opus', bitrate=24000, packet_loss=5, jitter=20); print(f'Benchmark completed: {success}')"
```

### Debugging

For more detailed output, use the Python logging module:

```bash
python -c "import logging; logging.basicConfig(level=logging.DEBUG); from voip_benchmark.rtp.simulator import simulate_rtp_transmission; success = simulate_rtp_transmission('audio/voip_ready.wav', 'results/output_debug.wav', codec='opus', bitrate=24000); print(f'Benchmark completed: {success}')"
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
python -c "import wave, numpy as np, struct; w = wave.open('audio/test_audio_30s.wav', 'w'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); data = np.sin(2 * np.pi * 440 * np.arange(0, 30, 1/48000)).astype(np.float32); w.writeframes(struct.pack('<%dh' % len(data), *(np.int16(data * 32767)))); w.close(); print('Created test audio file: audio/test_audio_30s.wav')"

# Convert to VoIP format
ffmpeg -i audio/test_audio_30s.wav -ar 8000 -ac 1 -acodec pcm_s16le audio/voip_ready.wav

# Verify the file exists
ls -l audio/voip_ready.wav
```

#### Python Module Import Errors

**Problem**: Import errors when running Python commands

**Solution**:
1. Make sure you're in the correct directory:
   ```bash
   cd deployment
   ```

2. Make sure dependencies are installed:
   ```bash
   pip install -r requirements.txt
   ```

3. Make sure the virtual environment is activated (if using):
   ```bash
   source .venv/bin/activate  # Linux/Mac
   # or
   .venv\Scripts\activate     # Windows
   ```