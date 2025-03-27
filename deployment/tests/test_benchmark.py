"""
Test suite for VoIP benchmarking functionality.

This module contains tests for the end-to-end benchmarking
capabilities of the VoIP benchmarking tool.
"""

import os
import pytest
import tempfile
import wave
import numpy as np
import subprocess
import time
from typing import Dict, List, Tuple

from voip_benchmark.codecs import get_codec
from voip_benchmark.codecs.opus import OpusCodec
from voip_benchmark.rtp.packet import RTPPacket
from voip_benchmark.rtp.session import RTPSession
import voip_benchmark.benchmark as benchmark


# Skip mark for tests that require external tools
requires_external_tools = pytest.mark.skipif(
    not (os.path.exists('/usr/bin/tshark') or os.path.exists('/usr/local/bin/tshark')),
    reason="tshark not found, skipping tests that require packet capture"
)


def create_test_wav_file(path: str, duration: float = 1.0, 
                         sample_rate: int = 48000, 
                         channels: int = 1) -> str:
    """Create a test WAV file for benchmarking.
    
    Args:
        path: Path to save the WAV file
        duration: Duration in seconds
        sample_rate: Sample rate in Hz
        channels: Number of audio channels
        
    Returns:
        Path to the created WAV file
    """
    # Generate sine wave
    samples = int(duration * sample_rate)
    t = np.linspace(0, duration, samples, False)
    tone = np.sin(2 * np.pi * 440 * t)
    
    # Scale to 16-bit range
    tone = (tone * 32767).astype(np.int16)
    
    # Create WAV file
    with wave.open(path, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)  # 16-bit PCM
        wav_file.setframerate(sample_rate)
        
        if channels == 1:
            wav_file.writeframes(tone.tobytes())
        else:
            # Duplicate for stereo
            stereo = np.column_stack([tone] * channels)
            wav_file.writeframes(stereo.tobytes())
    
    return path


def test_benchmark_wav_file_creation():
    """Test creating a test WAV file for benchmarking."""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
        temp_wav_path = temp_file.name
    
    try:
        # Create test WAV file
        path = create_test_wav_file(temp_wav_path, duration=0.5)
        
        # Verify the file exists
        assert os.path.exists(path)
        
        # Verify the file content
        with wave.open(path, 'rb') as wav_file:
            params = wav_file.getparams()
            assert params.nchannels == 1
            assert params.sampwidth == 2  # 16-bit
            assert params.framerate == 48000
            assert params.nframes > 0
            
            # Check total duration (within 1% tolerance)
            duration = params.nframes / params.framerate
            assert abs(duration - 0.5) < 0.005
    
    finally:
        # Clean up
        if os.path.exists(temp_wav_path):
            os.unlink(temp_wav_path)


def test_voip_compression_benchmark():
    """Test benchmarking of VoIP compression ratio."""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
        input_wav_path = temp_file.name
    
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
        output_wav_path = temp_file.name
    
    try:
        # Create test input WAV file
        create_test_wav_file(input_wav_path, duration=1.0)
        
        # Get input file size
        input_size = os.path.getsize(input_wav_path)
        
        # Initialize codec with different bitrates
        for bitrate in [8000, 24000, 64000]:
            # Benchmark compression for this bitrate
            result = benchmark.benchmark_codec_compression(
                input_file=input_wav_path,
                output_file=output_wav_path,
                codec_name='opus',
                bitrate=bitrate
            )
            
            # Verify result fields
            assert result['codec'] == 'opus'
            assert result['bitrate'] == bitrate
            assert result['input_size'] > 0
            assert result['compressed_size'] > 0
            assert result['output_size'] > 0
            assert 0 < result['compression_ratio'] < 1.0
            
            # For lower bitrates, expect better compression
            if bitrate == 8000:
                assert result['compression_ratio'] < 0.15  # Very efficient compression
            elif bitrate == 64000:
                # Less compression but still decent
                assert result['compression_ratio'] < 0.4
    
    finally:
        # Clean up
        for path in [input_wav_path, output_wav_path]:
            if os.path.exists(path):
                os.unlink(path)


@requires_external_tools
def test_network_traffic_benchmark():
    """Test benchmarking of network traffic."""
    # Skip test if running in CI environment without network access
    if os.environ.get('CI', 'false').lower() == 'true':
        pytest.skip("Skipping network test in CI environment")
    
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
        input_wav_path = temp_file.name
    
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
        output_wav_path = temp_file.name
        
    with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as temp_file:
        capture_path = temp_file.name
    
    try:
        # Create test input WAV file
        create_test_wav_file(input_wav_path, duration=1.0)
        
        # Benchmark network traffic
        result = benchmark.benchmark_network_traffic(
            input_file=input_wav_path,
            output_file=output_wav_path,
            capture_file=capture_path,
            codec_name='opus',
            bitrate=24000,
            packet_loss=0,
            jitter=0
        )
        
        # Verify result fields
        assert result['codec'] == 'opus'
        assert result['bitrate'] == 24000
        assert result['input_size'] > 0
        assert result['packets_sent'] > 0
        assert result['packets_received'] > 0
        assert result['bytes_sent'] > 0
        assert result['transmission_ratio'] > 0
        
        # Allow for some packet overhead, but it should be reasonable
        assert 0.8 < result['transmission_ratio'] < 1.5
    
    finally:
        # Clean up
        for path in [input_wav_path, output_wav_path, capture_path]:
            if os.path.exists(path):
                os.unlink(path)


@requires_external_tools
def test_network_simulation_benchmark():
    """Test benchmarking with network condition simulation."""
    # Skip test if running in CI environment without network access
    if os.environ.get('CI', 'false').lower() == 'true':
        pytest.skip("Skipping network test in CI environment")
    
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
        input_wav_path = temp_file.name
    
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
        output_wav_path = temp_file.name
        
    with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as temp_file:
        capture_path = temp_file.name
    
    try:
        # Create test input WAV file
        create_test_wav_file(input_wav_path, duration=1.0)
        
        # Benchmark with simulated packet loss and jitter
        result = benchmark.benchmark_network_traffic(
            input_file=input_wav_path,
            output_file=output_wav_path,
            capture_file=capture_path,
            codec_name='opus',
            bitrate=24000,
            packet_loss=5,  # 5% packet loss
            jitter=20  # 20ms jitter
        )
        
        # Verify result fields
        assert result['codec'] == 'opus'
        assert result['bitrate'] == 24000
        assert result['packet_loss'] == 5
        assert result['jitter'] == 20
        assert result['input_size'] > 0
        assert result['packets_sent'] > 0
        assert result['packets_received'] > 0
        assert result['bytes_sent'] > 0
        
        # With packet loss, there should be fewer received packets than sent
        assert result['packets_received'] <= result['packets_sent']
        
        # The packet loss should be approximately what we specified
        expected_received = result['packets_sent'] * (1 - 0.05)  # 5% loss
        tolerance = max(2, int(result['packets_sent'] * 0.03))  # Allow some variance
        
        # Check that packet loss is within expected range, with some tolerance
        assert abs(result['packets_received'] - expected_received) <= tolerance
    
    finally:
        # Clean up
        for path in [input_wav_path, output_wav_path, capture_path]:
            if os.path.exists(path):
                os.unlink(path) 