"""
Test suite for RTP and codec integration.

This module contains tests that verify the integration of RTP protocol
with audio codecs in the VoIP benchmarking tool.
"""

import os
import pytest
import tempfile
import wave
import numpy as np
import socket
import threading
import time
from typing import Tuple

from voip_benchmark.codecs import get_codec
from voip_benchmark.codecs.opus import OpusCodec
from voip_benchmark.rtp.packet import RTPPacket
from voip_benchmark.rtp.session import RTPSession


def create_test_audio(sample_rate: int = 48000, channels: int = 1, 
                      duration: float = 1.0) -> bytes:
    """Create test audio data for testing.
    
    Args:
        sample_rate: Audio sample rate in Hz
        channels: Number of audio channels
        duration: Duration in seconds
        
    Returns:
        PCM audio data as bytes
    """
    # Generate sine wave at 440 Hz
    samples = int(duration * sample_rate)
    t = np.linspace(0, duration, samples, False)
    tone = np.sin(2 * np.pi * 440 * t)
    
    # Scale to 16-bit range
    tone = (tone * 32767).astype(np.int16)
    
    # Convert to bytes
    if channels == 1:
        return tone.tobytes()
    else:
        # Duplicate for stereo
        stereo = np.column_stack([tone] * channels)
        return stereo.tobytes()


def test_rtp_packet_with_opus_payload():
    """Test creating an RTP packet with Opus-encoded payload."""
    # Create test audio data
    audio_data = create_test_audio(duration=0.1)  # Short audio clip
    
    # Initialize Opus codec
    codec = OpusCodec(frame_size=960)  # 20ms at 48kHz
    
    # Encode audio
    encoded_data = codec.encode(audio_data)
    
    # Create RTP packet with Opus payload
    packet = RTPPacket(
        payload_type=111,  # Dynamic payload type for Opus
        payload=encoded_data,
        sequence_number=1000,
        timestamp=48000,  # 1 second at 48kHz
        ssrc=0x12345678
    )
    
    # Check packet properties
    assert packet.payload_type == 111
    assert packet.payload == encoded_data
    assert packet.sequence_number == 1000
    assert packet.timestamp == 48000
    assert packet.ssrc == 0x12345678
    
    # Convert to bytes and back
    packet_bytes = packet.to_bytes()
    parsed_packet = RTPPacket.from_bytes(packet_bytes)
    
    # Check that the parsed packet matches the original
    assert parsed_packet.payload_type == packet.payload_type
    assert parsed_packet.payload == packet.payload
    assert parsed_packet.sequence_number == packet.sequence_number
    assert parsed_packet.timestamp == packet.timestamp
    assert parsed_packet.ssrc == packet.ssrc


def test_rtp_send_receive_with_opus():
    """Test sending and receiving RTP packets with Opus-encoded audio."""
    # Skip if running in CI environment without network support
    if os.environ.get('CI', 'false').lower() == 'true':
        pytest.skip("Skipping network test in CI environment")
    
    # Create test audio data
    audio_data = create_test_audio(duration=0.1)  # Short audio clip
    
    # Initialize Opus codec
    codec = OpusCodec(frame_size=960)  # 20ms at 48kHz
    
    # Encode audio
    encoded_data = codec.encode(audio_data)
    
    # Set up RTP sessions
    sender_session = RTPSession(local_port=12345)
    receiver_session = RTPSession(local_port=12346)
    
    # Set remote endpoints
    sender_session.set_remote_endpoint('127.0.0.1', 12346)
    
    # Create packet received event
    packet_received = threading.Event()
    received_packet = [None]  # Use a list to store the received packet
    
    # Define packet handler
    def packet_handler(packet):
        received_packet[0] = packet
        packet_received.set()
    
    try:
        # Open sessions
        sender_session.open()
        receiver_session.open()
        
        # Start receiving
        receiver_session.start_receiving(packet_handler)
        
        # Send packet
        sent_bytes = sender_session.send_packet(
            payload=encoded_data,
            payload_type=111  # Dynamic payload type for Opus
        )
        
        # Wait for packet to be received
        if not packet_received.wait(2.0):
            pytest.fail("Packet not received within timeout")
        
        # Check received packet
        assert received_packet[0] is not None
        assert received_packet[0].payload_type == 111
        assert received_packet[0].payload == encoded_data
        
        # Decode received audio
        decoded_data = codec.decode(received_packet[0].payload)
        
        # Check that decoded data is not empty
        assert len(decoded_data) > 0
        
    finally:
        # Close sessions
        sender_session.close()
        receiver_session.close()


def test_rtp_send_receive_compression_ratio():
    """Test the compression ratio of audio sent over RTP with Opus."""
    # Create test audio data
    audio_data = create_test_audio(duration=1.0)  # 1 second audio
    
    # Initialize Opus codec with different bitrates
    for bitrate in [8000, 24000, 64000]:
        codec = OpusCodec(bitrate=bitrate, frame_size=960)  # 20ms at 48kHz
        
        # Encode audio
        encoded_data = codec.encode(audio_data)
        
        # Calculate compression ratio
        compression_ratio = len(encoded_data) / len(audio_data)
        
        # Expected compression ratio should approximately match bitrate
        expected_ratio = bitrate / (48000 * 16 * 1)  # sample_rate * bit_depth * channels
        
        # Allow for some variation due to encoding overhead and packet headers
        # Opus is very efficient, so we expect good compression
        assert 0.01 < compression_ratio < 0.6
        
        # For lower bitrates, expect better compression
        if bitrate == 8000:
            assert compression_ratio < 0.15
        elif bitrate == 64000:
            assert compression_ratio < 0.4
            
        # Verify that the compression ratio is roughly proportional to the bitrate
        # This checks that the codec is properly honoring the bitrate setting
        if bitrate == 24000:
            ratio_24k = compression_ratio
        elif bitrate == 8000:
            ratio_8k = compression_ratio
            
    # The 24kbps ratio should be roughly 3x the 8kbps ratio
    # Allow for some variation due to encoding efficiency differences
    assert 1.5 < (ratio_24k / ratio_8k) < 4.0 