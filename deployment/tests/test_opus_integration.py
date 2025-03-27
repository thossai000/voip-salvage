"""
Integration tests for OpusCodec functionality.

This module tests the OpusCodec implementation to verify it works correctly
with the underlying opuslib library.
"""

import os
import sys
import struct
import math
import pytest
from typing import Tuple

# Add src directory to path if running test directly
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from voip_benchmark.codecs.opus import OpusCodec, PAYLOAD_TYPE_OPUS


@pytest.fixture
def sample_rates() -> list:
    """Test sample rates fixture."""
    return [8000, 16000, 24000, 48000]


@pytest.fixture
def bitrates() -> list:
    """Test bitrates fixture."""
    return [8000, 16000, 24000, 32000, 64000]


@pytest.fixture
def create_sine_wave():
    """Fixture to create a test sine wave."""
    def _create(frequency=440, duration_ms=20, sample_rate=48000, channels=1):
        """Create a sine wave test signal."""
        num_samples = int(sample_rate * duration_ms / 1000)
        samples = []
        
        for i in range(num_samples):
            value = int(32767 * math.sin(2 * math.pi * frequency * i / sample_rate))
            for _ in range(channels):
                samples.append(struct.pack('<h', value))  # Little-endian 16-bit
        
        return b''.join(samples)
    
    return _create


def test_opus_import():
    """Test that OpusCodec can be imported."""
    assert OpusCodec is not None
    assert PAYLOAD_TYPE_OPUS == 111


def test_opus_initialization():
    """Test OpusCodec initialization with default parameters."""
    codec = OpusCodec()
    assert codec is not None
    assert codec.sample_rate == 8000
    assert codec.channels == 1
    assert codec.payload_type == 111


@pytest.mark.parametrize("sample_rate", [8000, 16000, 24000, 48000])
@pytest.mark.parametrize("channels", [1, 2])
def test_opus_configuration(sample_rate, channels):
    """Test OpusCodec with various configuration parameters."""
    bitrate = 16000
    complexity = 10
    application = OpusCodec.APPLICATION_VOIP
    
    codec = OpusCodec(
        sample_rate=sample_rate,
        channels=channels,
        bitrate=bitrate,
        complexity=complexity,
        application=application
    )
    
    config = codec.get_config()
    assert config["sample_rate"] == sample_rate
    assert config["channels"] == channels
    assert config["bitrate"] == bitrate
    assert config["complexity"] == complexity
    assert config["application"] == application


def test_encode_decode(create_sine_wave):
    """Test encoding and decoding with the Opus codec."""
    # Initialize codec
    codec = OpusCodec(
        sample_rate=48000,
        channels=1,
        bitrate=16000,
        complexity=10,
        application=OpusCodec.APPLICATION_VOIP
    )
    
    # Create test audio data
    test_data = create_sine_wave(
        frequency=440,
        duration_ms=20,
        sample_rate=48000,
        channels=1
    )
    
    # Encode
    encoded_data = codec.encode(test_data)
    
    # Verify compression happened
    assert len(encoded_data) < len(test_data)
    
    # Decode
    decoded_data = codec.decode(encoded_data)
    
    # Verify size matches original
    assert len(decoded_data) == len(test_data)


def test_compression_ratio(create_sine_wave):
    """Test that the compression ratio is within expected range."""
    # Initialize codec with default values
    codec = OpusCodec(
        sample_rate=48000,
        channels=1,
        bitrate=16000
    )
    
    # Create test audio data (1 second)
    test_data = create_sine_wave(
        frequency=440,
        duration_ms=1000,  # 1 second
        sample_rate=48000,
        channels=1
    )
    
    # Encode in frames
    frame_size_ms = 20
    frame_size_bytes = 48000 * 1 * 2 * frame_size_ms // 1000  # sample_rate * channels * bytes_per_sample * ms / 1000
    total_encoded_size = 0
    
    for i in range(0, len(test_data), frame_size_bytes):
        frame = test_data[i:i+frame_size_bytes]
        # Pad if needed
        if len(frame) < frame_size_bytes:
            frame = frame + b'\x00' * (frame_size_bytes - len(frame))
        
        encoded = codec.encode(frame)
        total_encoded_size += len(encoded)
    
    # Calculate compression ratio
    compression_ratio = total_encoded_size / len(test_data)
    
    # At 16 kbps, a 48kHz mono signal (768 kbps) should compress to about 2% of original size
    assert compression_ratio < 0.1, f"Compression ratio ({compression_ratio:.4f}) is higher than expected"


def test_bitrate_change():
    """Test that the bitrate can be changed dynamically."""
    # Initialize codec with initial bitrate
    initial_bitrate = 16000
    codec = OpusCodec(
        sample_rate=48000,
        channels=1,
        bitrate=initial_bitrate
    )
    
    # Verify initial bitrate
    assert codec.bitrate == initial_bitrate
    
    # Change bitrate
    new_bitrate = 32000
    success = codec.set_bitrate(new_bitrate)
    
    # Verify change was successful
    assert success
    assert codec.bitrate == new_bitrate


if __name__ == "__main__":
    # Run tests directly if file is executed
    pytest.main(["-xvs", __file__])