"""
Unit tests for Opus codec implementation
"""

import pytest
import numpy as np
from voip_benchmark.codecs import OpusCodec

class TestOpusCodec:
    """Test suite for the Opus codec implementation"""
    
    @pytest.fixture
    def codec(self):
        """Create a default Opus codec instance for testing"""
        return OpusCodec(sample_rate=48000, channels=1)
        
    @pytest.fixture
    def audio_data(self):
        """Generate a simple sine wave for testing"""
        duration = 1.0  # seconds
        sample_rate = 48000
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        # 440 Hz sine wave
        return (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
    
    def test_initialization(self, codec):
        """Test that the codec initializes correctly"""
        assert codec.sample_rate == 48000
        assert codec.channels == 1
        assert codec.bitrate == 64000  # Default bitrate
        
    def test_set_bitrate(self, codec):
        """Test changing the bitrate"""
        codec.set_bitrate(96000)
        assert codec.bitrate == 96000
        
    def test_encode_decode(self, codec, audio_data):
        """Test encoding and decoding a simple audio sample"""
        # Encode the data
        encoded = codec.encode(audio_data)
        assert encoded is not None
        assert len(encoded) > 0
        
        # Decode the data
        decoded = codec.decode(encoded)
        assert decoded is not None
        assert len(decoded) > 0
        
        # Lengths should be approximately the same (might have slight differences
        # due to codec framing)
        assert abs(len(decoded) - len(audio_data)) < 100
        
    def test_compression_ratio(self, codec, audio_data):
        """Test that the compression ratio calculation works"""
        encoded = codec.encode(audio_data)
        ratio = codec.calculate_compression_ratio(audio_data, encoded)
        
        # Opus at 64kbps should compress the data significantly
        assert ratio > 1.0
        
    def test_encoder_cleanup(self, codec):
        """Test that the encoder cleans up resources"""
        codec.close()
        # Should not raise exceptions 