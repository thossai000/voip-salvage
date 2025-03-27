"""
Pytest configuration and fixtures for VoIP benchmarking tool tests.
"""

import os
import pytest
import tempfile
import wave
import numpy as np
import subprocess
import socket
from typing import Dict, List, Tuple


@pytest.fixture
def test_audio_data():
    """Create test audio data for testing.
    
    Returns:
        PCM audio data as bytes
    """
    # Generate sine wave at 440 Hz
    samples = 48000  # 1 second at 48kHz
    sample_rate = 48000
    t = np.linspace(0, 1, samples, False)
    tone = np.sin(2 * np.pi * 440 * t)
    
    # Scale to 16-bit range
    tone = (tone * 32767).astype(np.int16)
    
    # Convert to bytes
    return tone.tobytes()


@pytest.fixture
def test_wav_file():
    """Create a temporary WAV file for testing.
    
    Returns:
        Path to the temporary WAV file
    """
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
        temp_wav_path = temp_file.name
    
    # Generate sine wave
    samples = 48000  # 1 second at 48kHz
    sample_rate = 48000
    channels = 1
    
    t = np.linspace(0, 1, samples, False)
    tone = np.sin(2 * np.pi * 440 * t)
    tone = (tone * 32767).astype(np.int16)
    
    # Write WAV file
    with wave.open(temp_wav_path, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(tone.tobytes())
    
    yield temp_wav_path
    
    # Clean up
    if os.path.exists(temp_wav_path):
        os.unlink(temp_wav_path)


@pytest.fixture
def find_free_port():
    """Find a free port for testing.
    
    Returns:
        An available port number
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@pytest.fixture
def check_external_tools():
    """Check if external tools are available.
    
    Returns:
        Dict with tool availability
    """
    tools = {
        'tshark': os.path.exists('/usr/bin/tshark') or os.path.exists('/usr/local/bin/tshark'),
        'ffmpeg': os.path.exists('/usr/bin/ffmpeg') or os.path.exists('/usr/local/bin/ffmpeg')
    }
    
    return tools 