# VoIP Benchmarking Tool API Reference

This document provides a reference for the Python API of the VoIP benchmarking tool.

## Table of Contents

1. [Package Structure](#package-structure)
2. [Codec API](#codec-api)
3. [RTP API](#rtp-api)
4. [Utility Functions](#utility-functions)

## Package Structure

The VoIP benchmarking tool is organized as follows:

```
voip_benchmark/
├── __init__.py            # Package initialization
├── codecs/                # Codec implementations
│   ├── __init__.py        # Codec package initialization
│   ├── base.py            # Base codec classes and interfaces
│   └── opus.py            # Opus codec implementation
├── rtp/                   # RTP implementation
│   ├── __init__.py        # RTP package initialization
│   ├── packet.py          # RTP packet functionality
│   ├── session.py         # RTP session management
│   ├── simulator.py       # Network simulation for RTP
│   ├── sender.py          # RTP sender implementation
│   ├── receiver.py        # RTP receiver implementation
│   └── stream.py          # Stream handling for RTP
└── utils/                 # Utility functions
    └── ...
```

## Codec API

### CodecBase

Abstract base class for all codec implementations.

```python
class CodecBase:
    def __init__(self, sample_rate=48000, channels=1, **kwargs):
        """Initialize the codec.
        
        Args:
            sample_rate: Audio sample rate in Hz
            channels: Number of audio channels
            **kwargs: Additional codec-specific parameters
        """
        
    def encode(self, audio_data):
        """Encode audio data.
        
        Args:
            audio_data: Raw PCM audio data
            
        Returns:
            Encoded audio data
        """
        
    def decode(self, encoded_data):
        """Decode audio data.
        
        Args:
            encoded_data: Encoded audio data
            
        Returns:
            Raw PCM audio data
        """
        
    def get_bitrate(self):
        """Get the current bitrate of the codec.
        
        Returns:
            Current bitrate in bits per second
        """
```

### OpusCodec

Implementation of the Opus audio codec.

```python
class OpusCodec(CodecBase):
    def __init__(self, sample_rate=48000, channels=1, **kwargs):
        """Initialize the Opus codec.
        
        Args:
            sample_rate: Audio sample rate in Hz
            channels: Number of audio channels
            **kwargs: Codec-specific parameters
                - bitrate: Target bitrate in bits per second (default: 64000)
                - application: Application type (default: VOIP)
                - complexity: Computational complexity (0-10) (default: 10)
                - frame_size: Frame size in samples (default: 960)
        """
        
    def encode(self, audio_data):
        """Encode audio data with Opus.
        
        Args:
            audio_data: Raw PCM audio data
            
        Returns:
            Opus-encoded audio data
        """
        
    def decode(self, encoded_data):
        """Decode Opus-encoded audio data.
        
        Args:
            encoded_data: Opus-encoded audio data
            
        Returns:
            Raw PCM audio data
        """
        
    def get_bitrate(self):
        """Get the current bitrate of the Opus codec.
        
        Returns:
            Current bitrate in bits per second
        """
```

## RTP API

### RTPPacket

Class for creating, parsing, and manipulating RTP packets.

```python
class RTPPacket:
    def __init__(self, payload_type=111, payload=b'', sequence_number=None, 
                 timestamp=None, ssrc=None, marker=False):
        """Initialize an RTP packet.
        
        Args:
            payload_type: RTP payload type
            payload: Packet payload data
            sequence_number: Packet sequence number (auto-generated if None)
            timestamp: Packet timestamp (auto-generated if None)
            ssrc: Synchronization source identifier (auto-generated if None)
            marker: Marker bit (usually set for the first packet in a talk spurt)
        """
        
    def to_bytes(self):
        """Convert the RTP packet to bytes.
        
        Returns:
            Raw packet data
        """
        
    def get_header_length(self):
        """Get the length of the RTP header.
        
        Returns:
            Header length in bytes
        """
        
    def get_payload_length(self):
        """Get the length of the payload.
        
        Returns:
            Payload length in bytes
        """
```

### RTPSession

Class for managing RTP sessions, including packet transmission and reception.

```python
class RTPSession:
    def __init__(self, local_address='0.0.0.0', local_port=12345,
                 remote_address=None, remote_port=None, ssrc=None):
        """Initialize an RTP session.
        
        Args:
            local_address: Local IP address to bind to
            local_port: Local port to bind to
            remote_address: Remote IP address for sending packets (None for receive-only)
            remote_port: Remote port for sending packets (None for receive-only)
            ssrc: Synchronization source identifier (auto-generated if None)
        """
        
    def open(self):
        """Open the RTP session.
        
        Creates and binds the UDP socket for the RTP session.
        """
        
    def close(self):
        """Close the RTP session.
        
        Closes the UDP socket and stops the receive thread if running.
        """
        
    def set_remote_endpoint(self, address, port):
        """Set the remote endpoint for sending packets.
        
        Args:
            address: Remote IP address
            port: Remote port
        """
        
    def send_packet(self, packet):
        """Send an RTP packet.
        
        Args:
            packet: RTPPacket to send
            
        Returns:
            Number of bytes sent
        """
        
    def start_receiving(self, packet_handler=None):
        """Start receiving packets in a background thread.
        
        Args:
            packet_handler: Callback function for handling received packets
        """
        
    def stop_receiving(self):
        """Stop receiving packets."""
        
    def get_stats(self):
        """Get statistics about the RTP session.
        
        Returns:
            Dictionary containing session statistics
        """
```

### Simulator Functions

```python
def simulate_rtp_transmission(input_file, output_file, codec='opus', bitrate=24000, 
                              packet_loss=0, jitter=0, out_of_order=False):
    """Simulate an RTP transmission with network impairments.
    
    Args:
        input_file: Path to input WAV file
        output_file: Path to output WAV file
        codec: Codec to use ('opus' or 'none')
        bitrate: Codec bitrate (if applicable)
        packet_loss: Packet loss probability (0-100)
        jitter: Jitter in milliseconds
        out_of_order: Whether to simulate out-of-order packets
        
    Returns:
        True if successful, False otherwise
    """
```

## Utility Functions

### WAV File Handling

```python
def create_test_wav(output_file, duration=30, frequency=440, 
                    sample_rate=48000, channels=1):
    """Create a test WAV file with a sine wave.
    
    Args:
        output_file: Path to output WAV file
        duration: Duration in seconds
        frequency: Frequency of sine wave in Hz
        sample_rate: Sample rate in Hz
        channels: Number of channels
        
    Returns:
        Path to created WAV file
    """
    
def convert_to_voip_format(input_file, output_file):
    """Convert a WAV file to VoIP-friendly format.
    
    Args:
        input_file: Path to input WAV file
        output_file: Path to output WAV file
        
    Returns:
        Path to converted WAV file
    """
```

### Network Analysis

```python
def analyze_packet_capture(capture_file):
    """Analyze a packet capture file.
    
    Args:
        capture_file: Path to packet capture file
        
    Returns:
        Dictionary containing analysis results
    """
``` 