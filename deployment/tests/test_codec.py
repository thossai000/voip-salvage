"""
Test suite for codec functionality.

This module contains unit tests for the codec functionality in the
VoIP benchmarking tool, focusing on the Opus codec.
"""

import os
import pytest
import tempfile
import wave
import numpy as np
from typing import Tuple

from voip_benchmark.codecs import get_codec, AVAILABLE_CODECS
from voip_benchmark.codecs.base import CodecBase
from voip_benchmark.codecs.opus import OpusCodec


def create_test_audio(sample_rate: int = 48000, channels: int = 1, 
                      duration: float = 1.0) -> bytes:
    """Create test audio data for testing codecs.
    
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


def test_opus_codec_available():
    """Test that the Opus codec is available."""
    assert 'opus' in AVAILABLE_CODECS
    assert AVAILABLE_CODECS['opus'] == OpusCodec
    
    # Get the codec by name
    codec_class = get_codec('opus')
    assert codec_class == OpusCodec


def test_opus_codec_initialization():
    """Test the Opus codec initialization."""
    # Test default initialization
    codec = OpusCodec()
    assert codec.sample_rate == 48000
    assert codec.channels == 1
    assert codec.bitrate == 64000  # Default bitrate
    
    # Test custom initialization
    codec = OpusCodec(
        sample_rate=16000, 
        channels=2, 
        bitrate=32000,
        complexity=8
    )
    assert codec.sample_rate == 16000
    assert codec.channels == 2
    assert codec.bitrate == 32000
    assert codec.complexity == 8
    
    # Test invalid sample rate
    with pytest.raises(ValueError):
        OpusCodec(sample_rate=44100)  # Not supported by Opus
    
    # Test invalid channels
    with pytest.raises(ValueError):
        OpusCodec(channels=3)  # Opus supports 1 or 2 channels


def test_opus_codec_encode_decode():
    """Test the Opus codec encoding and decoding."""
    # Create test audio
    audio_data = create_test_audio()
    
    # Initialize codec
    codec = OpusCodec()
    
    # Encode audio
    encoded_data = codec.encode(audio_data)
    assert len(encoded_data) > 0
    assert len(encoded_data) < len(audio_data)  # Should be compressed
    
    # Decode audio
    decoded_data = codec.decode(encoded_data)
    assert len(decoded_data) > 0
    
    # Check that the decoded data is similar in size to the original
    # (may not be exactly the same due to compression)
    assert abs(len(decoded_data) - len(audio_data)) / len(audio_data) < 0.1


def test_opus_codec_bitrate():
    """Test the Opus codec bitrate setting."""
    codec = OpusCodec()
    
    # Set and get bitrate
    codec.set_bitrate(32000)
    assert codec.get_bitrate() == 32000
    
    # Test with low bitrate
    codec.set_bitrate(8000)
    assert codec.get_bitrate() == 8000
    
    # Test with high bitrate
    codec.set_bitrate(128000)
    assert codec.get_bitrate() == 128000


def test_opus_codec_compression_ratio():
    """Test the compression ratio of the Opus codec."""
    # Create test audio (1 second)
    audio_data = create_test_audio(duration=1.0)
    original_size = len(audio_data)
    
    # Initialize codec with different bitrates
    for bitrate in [8000, 16000, 32000, 64000, 128000]:
        codec = OpusCodec(bitrate=bitrate)
        
        # Encode audio
        encoded_data = codec.encode(audio_data)
        encoded_size = len(encoded_data)
        
        # Calculate compression ratio
        compression_ratio = encoded_size / original_size
        
        # Expected compression ratio should approximately match bitrate
        # Opus is typically very efficient, so we expect good compression
        expected_ratio = bitrate / (48000 * 16 * 1)  # sample_rate * bit_depth * channels
        
        # Allow for some variation due to encoding overhead
        assert 0.01 < compression_ratio < 0.6
        
        # The compression ratio should roughly correspond to the bitrate
        # Higher bitrates should give higher compression ratios
        if bitrate == 8000:
            # At very low bitrates, expect significant compression
            assert compression_ratio < 0.1
        elif bitrate == 128000:
            # At high bitrates, expect less compression
            assert compression_ratio > 0.1


def test_opus_codec_with_wav_file():
    """Test the Opus codec with a WAV file."""
    # Create a temporary WAV file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
        temp_wav_path = temp_file.name
    
    try:
        # Generate test WAV file
        samples = 48000  # 1 second at 48kHz
        sample_rate = 48000
        channels = 1
        
        # Create sine wave
        t = np.linspace(0, 1, samples, False)
        tone = np.sin(2 * np.pi * 440 * t)
        tone = (tone * 32767).astype(np.int16)
        
        # Write WAV file
        with wave.open(temp_wav_path, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(tone.tobytes())
        
        # Initialize codec
        codec = OpusCodec()
        
        # Read WAV file
        audio_data, wav_info = codec.read_wav_file(temp_wav_path)
        
        # Check WAV info
        assert wav_info['channels'] == channels
        assert wav_info['sample_rate'] == sample_rate
        assert wav_info['sample_width'] == 2  # 16-bit
        
        # Test encoding and decoding
        encoded_data = codec.encode(audio_data)
        decoded_data = codec.decode(encoded_data)
        
        # Check data sizes
        assert len(encoded_data) < len(audio_data)  # Should be compressed
        assert len(decoded_data) > 0
        
    finally:
        # Clean up
        if os.path.exists(temp_wav_path):
            os.unlink(temp_wav_path)


def test_opus_codec_multiple_frames():
    """Test the Opus codec with multiple frames."""
    # Create longer test audio (5 seconds)
    audio_data = create_test_audio(duration=5.0)
    
    # Initialize codec
    codec = OpusCodec(frame_size=960)  # 20ms at 48kHz
    
    # Encode audio
    encoded_data = codec.encode(audio_data)
    
    # Decode audio
    decoded_data = codec.decode(encoded_data)
    
    # Check data sizes
    assert len(encoded_data) < len(audio_data)  # Should be compressed
    assert abs(len(decoded_data) - len(audio_data)) / len(audio_data) < 0.1 