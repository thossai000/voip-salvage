# VoIP Benchmarking Tool Technical Reference

This document provides detailed technical information about the implementation of the VoIP benchmarking tool.

## Table of Contents

1. [RTP Implementation](#rtp-implementation)
2. [Opus Codec Implementation](#opus-codec-implementation)
3. [Network Simulation](#network-simulation)
4. [Benchmarking Methodology](#benchmarking-methodology)
5. [System Architecture](#system-architecture)

## RTP Implementation

### RTP Packet Structure

The RTP (Real-time Transport Protocol) implementation follows [RFC 3550](https://tools.ietf.org/html/rfc3550). Each RTP packet consists of:

1. **Fixed header** (12 bytes):
   - Version (2 bits): Set to 2
   - Padding (1 bit): Indicates if padding bytes are present
   - Extension (1 bit): Indicates if header extension is present
   - CSRC Count (4 bits): Number of CSRC identifiers
   - Marker (1 bit): Interpretation defined by profile
   - Payload Type (7 bits): Format of payload data
   - Sequence Number (16 bits): Increments for each packet sent
   - Timestamp (32 bits): Sampling instant of first byte
   - SSRC (32 bits): Synchronization source identifier

2. **CSRC identifiers** (optional, 0-15 items, 4 bytes each)

3. **Payload data** (variable length)

The implementation provides the following features:
- Generation of correct RTP headers
- Automatic sequence numbering and timestamp incrementing
- Proper payload type setting based on codec
- Support for marker bits to indicate speech boundaries

### RTP Session Management

The `RTPSession` class manages UDP socket communication for RTP packets:

- Socket creation and binding to specified local address and port
- Setting remote endpoints for packet transmission
- Concurrent packet reception using a background thread
- Gathering of transmission statistics (packets sent/received, bytes sent/received)
- Proper cleanup of resources on session termination

## Opus Codec Implementation

### Opus Features

The Opus codec implementation leverages [RFC 6716](https://tools.ietf.org/html/rfc6716) through the `opuslib` Python binding. Key features include:

- Variable bitrate encoding (6 kbps to 510 kbps)
- Support for multiple sample rates (8 kHz to 48 kHz)
- Low algorithmic delay (5 ms to 66.5 ms)
- Multiple application modes:
  - VOIP: Optimized for speech
  - AUDIO: Optimized for music
  - RESTRICTED_LOWDELAY: Reduced algorithmic delay

### Encoding/Decoding Process

The encoding process involves:
1. Configuring the Opus encoder with appropriate parameters
2. Converting raw PCM audio data to Opus-encoded format
3. Packetizing encoded data for transmission

The decoding process involves:
1. Extracting Opus-encoded data from received packets
2. Decoding back to raw PCM format
3. Handling potential packet loss with Opus's built-in loss concealment

### Opus RTP Integration

The integration of Opus with RTP follows [RFC 7587](https://tools.ietf.org/html/rfc7587):

- Uses dynamic payload type (default 111)
- Configures appropriate sampling rate and channel count
- Handles frame sizes correctly (2.5, 5, 10, 20, 40, or 60 ms)
- Properly sets RTP timestamp increments based on frame size

## Network Simulation

### Packet Loss Simulation

Packet loss is simulated using a simple probabilistic model:
- Each packet has a specified probability of being dropped
- Random number generation determines if a packet will be dropped
- No correlation between consecutive packet losses (simple model)

### Jitter Simulation

Network jitter is simulated by:
- Adding random delays to packet transmission
- Using a normal distribution with mean 0 and specified standard deviation
- Ensuring minimum delay remains positive
- Optionally implementing temporal correlation between delays

### Out-of-Order Packet Simulation

Out-of-order packet delivery is simulated by:
- Temporarily holding a percentage of packets
- Releasing held packets after a short delay
- Preserving original RTP sequence numbers

## Benchmarking Methodology

### Metrics Collection

The benchmarking system collects the following metrics:
- **Packet counts**: Total packets sent and received
- **Byte counts**: Total bytes sent and received
- **Packet loss rate**: Percentage of packets lost during transmission
- **Effective bandwidth**: Measured in bits per second
- **Compression ratio**: Ratio of compressed size to original size
- **Transmission ratio**: Ratio of transmitted bytes to original file size
- **Header overhead**: Additional bytes due to RTP headers

### Test Procedure

The standard benchmark procedure follows these steps:
1. Create or load a test WAV file
2. Convert the file to VoIP-friendly format (8 kHz, mono, PCM)
3. Start the RTP receiver (in a separate thread or process)
4. Begin packet capture (using tshark)
5. Transmit the audio file using the RTP sender with specified codec
6. Wait for transmission to complete
7. Analyze the packet capture
8. Calculate performance metrics
9. Generate report

### Output Files

Each benchmark produces the following output files:
- **Received audio file**: The reconstructed audio after transmission
- **Packet capture file**: Raw network traffic in PCAPNG format
- **RTP stream analysis**: Summary of RTP streams from tshark
- **Benchmark results**: CSV or JSON file with collected metrics

## System Architecture

### Component Interaction

The VoIP benchmarking system consists of the following components:

1. **Audio Processing**:
   - WAV file creation and conversion
   - Audio format validation
   - PCM data handling

2. **Codec Layer**:
   - Codec selection and initialization
   - Audio encoding and decoding
   - Bitrate and quality configuration

3. **RTP Layer**:
   - Packet creation and parsing
   - Session management
   - Transmission and reception

4. **Network Analysis**:
   - Packet capture setup
   - Traffic analysis
   - Metrics calculation

5. **Benchmark Orchestration**:
   - Test configuration
   - Component coordination
   - Results collection and reporting

### Docker Integration

The system integrates with Docker in the following ways:

1. **Container Discovery**:
   - Automatic identification of Jitsi Meet containers
   - IP address resolution for container-to-container communication

2. **Network Configuration**:
   - Using Docker bridge network for communication
   - Proper port exposure for RTP traffic

3. **Resource Management**:
   - Setting appropriate resource limits for containers
   - Preventing container overutilization during tests

### Extensibility

The system is designed to be extensible in the following areas:

1. **Codec Support**:
   - Abstract base class for codecs
   - Easy integration of additional codecs

2. **Network Simulation**:
   - Configurable packet loss models
   - Customizable jitter simulation
   - Extensible network condition profiles

3. **Metrics Collection**:
   - Pluggable metric collectors
   - Custom analysis functions
   - Flexible reporting formats 