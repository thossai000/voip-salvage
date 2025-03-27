# VoIP Benchmarking Framework

A Python framework for benchmarking Voice over IP (VoIP) audio quality under various network conditions.

## Overview

This package provides tools for simulating and testing VoIP communications, with features for:

- Audio encoding/decoding with different codecs (currently supports Opus)
- RTP packet handling and streaming
- Network condition simulation (jitter, packet loss, latency)
- Adaptive bitrate control
- Audio quality metrics calculation
- Configuration management

## Structure

```
voip_benchmark/
├── codecs/              # Audio codec implementations
│   ├── adaptive_bitrate.py  # Adaptive bitrate control
│   ├── base.py          # Base codec class
│   └── opus.py          # Opus codec implementation
├── rtp/                 # RTP protocol implementation
│   ├── packet.py        # RTP packet handling
│   ├── session.py       # RTP session management
│   ├── stream.py        # RTP streaming
│   └── network.py       # Network condition simulation
└── utils/               # Utility functions
    ├── audio.py         # Audio processing utilities
    ├── config.py        # Configuration management
    ├── statistics.py    # Quality metrics calculation
    └── logging.py       # Logging utilities
```

## Requirements

- Python 3.8+
- opuslib
- numpy
- scipy

## Usage Example

```python
from voip_benchmark import get_codec, RTPSession, NetworkSimulator
from voip_benchmark.utils import read_wav_file, get_default_config

# Load audio file
audio_data, sample_rate = read_wav_file("input.wav")

# Get codec instance
codec = get_codec("opus")(sample_rate=sample_rate, channels=1)

# Encode audio
encoded = codec.encode_file(audio_data)

# Set up network simulation
network = NetworkSimulator(packet_loss=0.05, jitter=20)

# Set up RTP session
session = RTPSession(local_port=12345)
session.set_remote_endpoint("127.0.0.1", 54321)

# Transmit audio through simulated network
for packet in encoded:
    session.send_packet(packet, network)
``` 