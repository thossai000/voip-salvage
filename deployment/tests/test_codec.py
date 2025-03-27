#!/usr/bin/env python3
"""
Unit tests for the Opus codec implementation.

These tests verify the functionality of the Opus codec 
implementation in the voip_benchmark package.
"""

import os
import sys
import wave
import pytest
import tempfile
from pathlib import Path

# Add the parent directory to the path for importing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voip_benchmark.codecs.opus import Codec, OpusCodec


@pytest.fixture
def test_wav_file():
    """Create a temporary test WAV file."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_path = temp_file.name
    
    # Create a simple WAV file
    with wave.open(temp_path, 'wb') as wav_file:
        # Configure WAV file
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16 bits
        wav_file.setframerate(8000)  # 8 kHz
        
        # Generate 1 second of silence (all zeros)
        wav_file.writeframes(b'\x00\x00' * 8000)
    
    # Return the path to the test file
    yield temp_path
    
    # Clean up
    os.unlink(temp_path)


@pytest.fixture
def opus_codec():
    """Create an OpusCodec instance for testing."""
    return OpusCodec(
        sample_rate=8000,
        channels=1,
        bitrate=16000,
        complexity=10,
        application=OpusCodec.APPLICATION_VOIP,
        frame_size=160,  # 20ms at 8kHz
    )


def test_codec_instantiation():
    """Test that the OpusCodec can be instantiated with default values."""
    codec = OpusCodec()
    assert codec is not None
    assert codec.sample_rate == 8000
    assert codec.channels == 1
    assert codec.payload_type == 111


def test_opus_codec_configuration():
    """Test the OpusCodec configuration options."""
    codec = OpusCodec(
        sample_rate=16000,
        channels=2,
        bitrate=32000,
        complexity=5,
        application=OpusCodec.APPLICATION_AUDIO,
        frame_size=320,
        payload_type=100,
    )
    
    config = codec.get_config()
    assert config["sample_rate"] == 16000
    assert config["channels"] == 2
    assert config["bitrate"] == 32000
    assert config["complexity"] == 5
    assert config["application"] == OpusCodec.APPLICATION_AUDIO
    assert config["frame_size"] == 320
    assert config["payload_type"] == 100


def test_invalid_sample_rate():
    """Test that OpusCodec rejects invalid sample rates."""
    with pytest.raises(ValueError):
        OpusCodec(sample_rate=22050)  # Not in (8000, 12000, 16000, 24000, 48000)


def test_invalid_channels():
    """Test that OpusCodec rejects invalid channel counts."""
    with pytest.raises(ValueError):
        OpusCodec(channels=3)  # Not in (1, 2)


def test_invalid_bitrate():
    """Test that OpusCodec rejects invalid bitrates."""
    with pytest.raises(ValueError):
        OpusCodec(bitrate=4000)  # Below 6000
    
    with pytest.raises(ValueError):
        OpusCodec(bitrate=600000)  # Above 510000


def test_invalid_complexity():
    """Test that OpusCodec rejects invalid complexity values."""
    with pytest.raises(ValueError):
        OpusCodec(complexity=-1)  # Below 0
    
    with pytest.raises(ValueError):
        OpusCodec(complexity=11)  # Above 10


def test_invalid_application():
    """Test that OpusCodec rejects invalid application modes."""
    with pytest.raises(ValueError):
        OpusCodec(application=1234)  # Not a valid application mode


def test_encode_decode(opus_codec, test_wav_file):
    """Test encoding and decoding with Opus codec."""
    # Read the test WAV file
    with wave.open(test_wav_file, 'rb') as wav_file:
        pcm_data = wav_file.readframes(wav_file.getnframes())
    
    # Use a single 20ms frame for the test
    frame_size_bytes = 2 * 160  # 2 bytes per sample, 160 samples per frame (20ms)
    frame = pcm_data[:frame_size_bytes]
    
    # Pad if needed
    if len(frame) < frame_size_bytes:
        frame = frame + b'\x00' * (frame_size_bytes - len(frame))
    
    # Encode the PCM data
    encoded_data = opus_codec.encode(frame)
    
    # Check that encoding produces smaller data
    assert len(encoded_data) < len(frame)
    
    # Decode the encoded data
    decoded_data = opus_codec.decode(encoded_data)
    
    # Check that decoded data has the same length as the original frame
    assert len(decoded_data) == len(frame)


def test_compression_ratio(opus_codec, test_wav_file):
    """Test that Opus achieves significant compression."""
    # Read the test WAV file
    with wave.open(test_wav_file, 'rb') as wav_file:
        pcm_data = wav_file.readframes(wav_file.getnframes())
    
    # Process audio in 20ms frames
    frame_size_bytes = 2 * 160  # 2 bytes per sample, 160 samples per frame (20ms)
    compressed_data = bytearray()
    
    for i in range(0, len(pcm_data), frame_size_bytes):
        frame = pcm_data[i:i+frame_size_bytes]
        # Pad the last frame if needed
        if len(frame) < frame_size_bytes:
            frame = frame + b'\x00' * (frame_size_bytes - len(frame))
        
        # Encode frame
        encoded = opus_codec.encode(frame)
        compressed_data.extend(encoded)
    
    # Calculate compression ratio
    ratio = len(compressed_data) / len(pcm_data)
    
    # At 16 kbps, we expect significant compression (ratio < 0.3)
    assert ratio < 0.3
    
    # Verify compression is at least 70%
    assert ratio <= 0.3, f"Compression ratio {ratio} does not meet minimum 70% compression target"


def test_round_trip_integrity(opus_codec, test_wav_file):
    """Test that audio can be encoded and decoded without critical data loss."""
    # Create a new temporary file for the round-trip output
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        output_path = temp_file.name
    
    try:
        # Read the test WAV file
        with wave.open(test_wav_file, 'rb') as wav_in:
            sample_width = wav_in.getsampwidth()
            channels = wav_in.getnchannels()
            sample_rate = wav_in.getframerate()
            pcm_data = wav_in.readframes(wav_in.getnframes())
        
        # Process audio in 20ms frames
        frame_size_bytes = sample_width * channels * int(0.02 * sample_rate)
        encoded_frames = []
        
        for i in range(0, len(pcm_data), frame_size_bytes):
            frame = pcm_data[i:i+frame_size_bytes]
            # Pad the last frame if needed
            if len(frame) < frame_size_bytes:
                frame = frame + b'\x00' * (frame_size_bytes - len(frame))
            
            # Encode frame
            encoded = opus_codec.encode(frame)
            encoded_frames.append(encoded)
        
        # Decode all frames
        decoded_data = bytearray()
        for encoded_frame in encoded_frames:
            decoded_frame = opus_codec.decode(encoded_frame)
            decoded_data.extend(decoded_frame)
        
        # Write the decoded data to the output file
        with wave.open(output_path, 'wb') as wav_out:
            wav_out.setnchannels(channels)
            wav_out.setsampwidth(sample_width)
            wav_out.setframerate(sample_rate)
            wav_out.writeframes(decoded_data[:len(pcm_data)])  # Trim to original size
        
        # Verify the file was created
        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0
        
        # Verify the output file is a valid WAV file
        with wave.open(output_path, 'rb') as wav_check:
            assert wav_check.getnchannels() == channels
            assert wav_check.getsampwidth() == sample_width
            assert wav_check.getframerate() == sample_rate
            # Should have approximately the same number of frames
            assert abs(wav_check.getnframes() - wav_in.getnframes()) <= 20
    
    finally:
        # Clean up
        if os.path.exists(output_path):
            os.unlink(output_path)


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])