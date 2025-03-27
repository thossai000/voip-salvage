"""
Test suite for Opus codec integration.

This module contains tests for the integration of the Opus codec
with other components of the VoIP benchmarking tool.
"""

import os
import pytest
import tempfile
import wave
import numpy as np
import time
from typing import Dict, List, Tuple

from voip_benchmark.codecs import get_codec
from voip_benchmark.codecs.opus import OpusCodec
from voip_benchmark.codecs.adaptive_bitrate import AdaptiveBitrateController


def test_opus_codec_with_wav_reading():
    """Test the integration of Opus codec with WAV file reading."""
    # Create a test WAV file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
        temp_wav_path = temp_file.name
    
    try:
        # Generate a simple test WAV file
        sample_rate = 48000
        duration = 0.5  # seconds
        samples = int(duration * sample_rate)
        t = np.linspace(0, duration, samples, False)
        tone = np.sin(2 * np.pi * 440 * t)  # 440 Hz sine wave
        tone = (tone * 32767).astype(np.int16)  # 16-bit PCM
        
        with wave.open(temp_wav_path, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(tone.tobytes())
        
        # Initialize Opus codec
        codec = OpusCodec()
        
        # Read WAV file using the codec's functionality
        audio_data, wav_info = codec.read_wav_file(temp_wav_path)
        
        # Verify WAV info
        assert wav_info['channels'] == 1
        assert wav_info['sample_rate'] == sample_rate
        assert wav_info['sample_width'] == 2
        
        # Encode and decode the audio
        encoded_data = codec.encode(audio_data)
        decoded_data = codec.decode(encoded_data)
        
        # Check that the data size is as expected
        assert len(audio_data) == samples * 2  # 2 bytes per sample
        assert len(encoded_data) < len(audio_data)  # Should be compressed
        
        # Write the decoded audio to a new WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as out_temp_file:
            output_wav_path = out_temp_file.name
            
        try:
            with wave.open(output_wav_path, 'wb') as wav_file:
                wav_file.setnchannels(wav_info['channels'])
                wav_file.setsampwidth(wav_info['sample_width'])
                wav_file.setframerate(wav_info['sample_rate'])
                wav_file.writeframes(decoded_data)
            
            # Verify the output file exists and has valid content
            assert os.path.exists(output_wav_path)
            
            with wave.open(output_wav_path, 'rb') as wav_file:
                output_params = wav_file.getparams()
                assert output_params.nchannels == 1
                assert output_params.sampwidth == 2
                assert output_params.framerate == sample_rate
                
                # The frame count might be slightly different due to encoding/decoding
                # Just check that it's close to the original
                assert abs(output_params.nframes - samples) / samples < 0.1
                
        finally:
            # Clean up the output file
            if os.path.exists(output_wav_path):
                os.unlink(output_wav_path)
                
    finally:
        # Clean up the input file
        if os.path.exists(temp_wav_path):
            os.unlink(temp_wav_path)


def test_opus_codec_with_different_sample_rates():
    """Test Opus codec with different sample rates."""
    # Test different sample rates supported by Opus
    for sample_rate in [8000, 16000, 24000, 48000]:
        # Generate a sine wave with the current sample rate
        duration = 0.2  # seconds
        samples = int(duration * sample_rate)
        t = np.linspace(0, duration, samples, False)
        tone = np.sin(2 * np.pi * 440 * t)
        tone = (tone * 32767).astype(np.int16)
        audio_data = tone.tobytes()
        
        # Initialize Opus codec with this sample rate
        codec = OpusCodec(sample_rate=sample_rate)
        
        # Encode and decode audio
        encoded_data = codec.encode(audio_data)
        decoded_data = codec.decode(encoded_data)
        
        # Check that data was processed correctly
        assert len(encoded_data) > 0
        assert len(encoded_data) < len(audio_data)  # Should be compressed
        assert len(decoded_data) > 0
        
        # For sample rates other than 48kHz, the frame size needs to be adjusted
        expected_frame_size = 960 * sample_rate // 48000
        assert codec.frame_size // codec.channels == expected_frame_size


def test_opus_codec_with_adaptive_bitrate():
    """Test integration of Opus codec with adaptive bitrate control."""
    # Initialize Opus codec with default settings
    codec = OpusCodec(bitrate=32000)
    
    # Initialize adaptive bitrate controller
    controller = AdaptiveBitrateController(
        codec,
        min_bitrate=8000,
        max_bitrate=128000,
        adjustment_interval=0.1  # Short interval for testing
    )
    
    # Generate audio data
    duration = 0.5  # seconds
    sample_rate = 48000
    samples = int(duration * sample_rate)
    t = np.linspace(0, duration, samples, False)
    tone = np.sin(2 * np.pi * 440 * t)
    tone = (tone * 32767).astype(np.int16)
    audio_data = tone.tobytes()
    
    # Test encoding with different network conditions
    
    # Test 1: Good network conditions
    controller.network_stats.reset()
    for _ in range(50):
        controller.network_stats.add_packet(100, 0, False)
    
    # Encode audio data
    encoded_data = codec.encode(audio_data)
    
    # Update bitrate based on network conditions
    initial_bitrate = codec.bitrate
    controller.update_bitrate()
    
    # Bitrate should increase with good network
    assert codec.bitrate >= initial_bitrate
    
    # Encode audio again with new bitrate
    encoded_data_2 = codec.encode(audio_data)
    
    # Higher bitrate should result in larger encoded data
    # (though this might not always be true due to compression efficiency)
    if codec.bitrate > initial_bitrate * 1.5:  # Only check if bitrate increased significantly
        assert len(encoded_data_2) >= len(encoded_data) * 0.9  # Allow for some variation
    
    # Test 2: Poor network conditions
    controller.network_stats.reset()
    for _ in range(40):
        controller.network_stats.add_packet(100, 0, False)
    for _ in range(10):
        controller.network_stats.add_packet_loss()
    
    # Update bitrate again
    previous_bitrate = codec.bitrate
    controller.update_bitrate()
    
    # Bitrate should decrease with packet loss
    assert codec.bitrate < previous_bitrate
    
    # Encode audio again with reduced bitrate
    encoded_data_3 = codec.encode(audio_data)
    
    # Lower bitrate should result in smaller encoded data
    # (again, this might not always be true)
    if codec.bitrate < previous_bitrate * 0.7:  # Only check if bitrate decreased significantly
        assert len(encoded_data_3) <= len(encoded_data_2) * 1.1  # Allow for some variation 