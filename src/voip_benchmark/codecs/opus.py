"""
Opus Codec Implementation

This module provides an implementation of the Opus audio codec
for VoIP benchmarking.
"""

import os
import ctypes
import struct
from typing import Optional, Dict, Any

try:
    import opuslib
    from opuslib import api
    from opuslib.exceptions import OpusError
    OPUS_AVAILABLE = True
except ImportError:
    # Fallback to dummy implementation if opuslib is not available
    OPUS_AVAILABLE = False
    
from voip_benchmark.codecs.base import CodecBase


# Opus application types
OPUS_APPLICATION_VOIP = 2048
OPUS_APPLICATION_AUDIO = 2049
OPUS_APPLICATION_RESTRICTED_LOWDELAY = 2051

# Default Opus settings
DEFAULT_OPUS_BITRATE = 64000  # 64 kbps
DEFAULT_OPUS_FRAME_SIZE = 960  # 20ms at 48kHz
DEFAULT_OPUS_APPLICATION = OPUS_APPLICATION_VOIP
DEFAULT_OPUS_COMPLEXITY = 10  # Maximum quality

# Opus error codes and messages
OPUS_OK = 0
OPUS_ERROR_MESSAGES = {
    -1: "One or more invalid/out of range arguments",
    -2: "Not enough bytes allocated in the buffer",
    -3: "An internal error was detected",
    -4: "The compressed data passed is corrupted",
    -5: "Invalid/unsupported request number",
    -6: "An encoder or decoder structure is invalid"
}


class OpusCodec(CodecBase):
    """Opus codec implementation.
    
    This class provides an implementation of the Opus codec using the
    opuslib Python binding for libopus.
    """
    
    def __init__(self, sample_rate: int = 48000, channels: int = 1, **kwargs):
        """Initialize the Opus codec.
        
        Args:
            sample_rate: Audio sample rate in Hz (8000, 12000, 16000, 24000, or 48000)
            channels: Number of audio channels (1 or 2)
            **kwargs: Additional codec-specific parameters
                - bitrate: Target bitrate in bits per second
                - application: Application type (VOIP, AUDIO, or RESTRICTED_LOWDELAY)
                - complexity: Computational complexity (0-10, higher is better quality)
                - frame_size: Frame size in samples
        """
        if not OPUS_AVAILABLE:
            raise ImportError("opuslib is required for OpusCodec. Install with 'pip install opuslib'")
            
        # Validate sample rate
        valid_sample_rates = [8000, 12000, 16000, 24000, 48000]
        if sample_rate not in valid_sample_rates:
            raise ValueError(f"Sample rate {sample_rate} not supported. Must be one of {valid_sample_rates}")
            
        # Validate channels
        if channels not in [1, 2]:
            raise ValueError(f"Channels {channels} not supported. Must be 1 or 2")
            
        super().__init__(sample_rate, channels, **kwargs)
    
    def _configure(self, **kwargs) -> None:
        """Configure the Opus codec.
        
        Args:
            **kwargs: Codec-specific parameters
                - bitrate: Target bitrate in bits per second
                - application: Application type (VOIP, AUDIO, or RESTRICTED_LOWDELAY)
                - complexity: Computational complexity (0-10, higher is better quality)
                - frame_size: Frame size in samples
        """
        # Set default parameters
        self.bitrate = kwargs.get('bitrate', DEFAULT_OPUS_BITRATE)
        self.application = kwargs.get('application', DEFAULT_OPUS_APPLICATION)
        self.complexity = kwargs.get('complexity', DEFAULT_OPUS_COMPLEXITY)
        self.frame_size = kwargs.get('frame_size', DEFAULT_OPUS_FRAME_SIZE)
        
        # Create encoder and decoder
        self._create_encoder()
        self._create_decoder()
        
        self.initialized = True
    
    def _create_encoder(self) -> None:
        """Create and configure the Opus encoder."""
        error = ctypes.c_int()
        self.encoder = api.opus_encoder_create(
            self.sample_rate, 
            self.channels, 
            self.application, 
            ctypes.byref(error)
        )
        
        if error.value != OPUS_OK:
            raise OpusError(f"Failed to create Opus encoder: {OPUS_ERROR_MESSAGES.get(error.value, 'Unknown error')}")
        
        # Set encoder parameters
        api.opus_encoder_ctl(self.encoder, api.OPUS_SET_BITRATE(self.bitrate))
        api.opus_encoder_ctl(self.encoder, api.OPUS_SET_COMPLEXITY(self.complexity))
    
    def _create_decoder(self) -> None:
        """Create and configure the Opus decoder."""
        error = ctypes.c_int()
        self.decoder = api.opus_decoder_create(
            self.sample_rate,
            self.channels,
            ctypes.byref(error)
        )
        
        if error.value != OPUS_OK:
            raise OpusError(f"Failed to create Opus decoder: {OPUS_ERROR_MESSAGES.get(error.value, 'Unknown error')}")
    
    def encode(self, audio_data: bytes) -> bytes:
        """Encode audio data using Opus.
        
        Args:
            audio_data: Raw PCM audio data
            
        Returns:
            Opus-encoded audio data with packet length prefix
        """
        if not self.initialized:
            raise RuntimeError("Codec not initialized")
            
        # Calculate number of samples
        bytes_per_sample = 2  # 16-bit PCM
        total_samples = len(audio_data) // (bytes_per_sample * self.channels)
        
        # Process frame by frame
        encoded_frames = []
        for i in range(0, total_samples, self.frame_size):
            # Extract frame
            frame_start = i * bytes_per_sample * self.channels
            frame_end = min(frame_start + (self.frame_size * bytes_per_sample * self.channels), len(audio_data))
            frame = audio_data[frame_start:frame_end]
            
            # If the frame is smaller than expected, pad with zeros
            if len(frame) < self.frame_size * bytes_per_sample * self.channels:
                padding = b'\x00' * (self.frame_size * bytes_per_sample * self.channels - len(frame))
                frame += padding
            
            # Encode frame
            pcm = ctypes.cast(frame, ctypes.POINTER(ctypes.c_int16))
            max_data_bytes = len(frame)
            data = (ctypes.c_char * max_data_bytes)()
            
            encoded_size = api.opus_encode(
                self.encoder, 
                pcm, 
                self.frame_size, 
                data, 
                max_data_bytes
            )
            
            if encoded_size < 0:
                raise OpusError(f"Encoding failed: {OPUS_ERROR_MESSAGES.get(encoded_size, 'Unknown error')}")
                
            # Pack encoded frame with size prefix
            encoded_frame = struct.pack('!H', encoded_size) + ctypes.string_at(data, encoded_size)
            encoded_frames.append(encoded_frame)
        
        # Combine all encoded frames
        return b''.join(encoded_frames)
    
    def decode(self, encoded_data: bytes) -> bytes:
        """Decode Opus-encoded audio data.
        
        Args:
            encoded_data: Opus-encoded audio data with packet length prefix
            
        Returns:
            Raw PCM audio data
        """
        if not self.initialized:
            raise RuntimeError("Codec not initialized")
            
        decoded_frames = []
        offset = 0
        
        while offset < len(encoded_data):
            # Read packet size
            if offset + 2 > len(encoded_data):
                break
                
            packet_size = struct.unpack('!H', encoded_data[offset:offset+2])[0]
            offset += 2
            
            if offset + packet_size > len(encoded_data):
                break
                
            # Extract packet
            packet = encoded_data[offset:offset+packet_size]
            offset += packet_size
            
            # Decode packet
            pcm_size = self.frame_size * self.channels * 2  # 16-bit samples
            pcm = (ctypes.c_int16 * (self.frame_size * self.channels))()
            
            decoded_size = api.opus_decode(
                self.decoder,
                packet,
                packet_size,
                ctypes.cast(pcm, ctypes.POINTER(ctypes.c_int16)),
                self.frame_size,
                0  # No FEC
            )
            
            if decoded_size < 0:
                raise OpusError(f"Decoding failed: {OPUS_ERROR_MESSAGES.get(decoded_size, 'Unknown error')}")
                
            # Convert to bytes
            decoded_frame = ctypes.string_at(pcm, decoded_size * self.channels * 2)
            decoded_frames.append(decoded_frame)
        
        # Combine all decoded frames
        return b''.join(decoded_frames)
    
    def get_bitrate(self) -> int:
        """Get the current bitrate of the codec.
        
        Returns:
            Current bitrate in bits per second
        """
        if not self.initialized:
            return self.bitrate
            
        bitrate = ctypes.c_int()
        api.opus_encoder_ctl(self.encoder, api.OPUS_GET_BITRATE(ctypes.byref(bitrate)))
        return bitrate.value
    
    def set_bitrate(self, bitrate: int) -> None:
        """Set the bitrate of the codec.
        
        Args:
            bitrate: Bitrate in bits per second
        """
        if not self.initialized:
            self.bitrate = bitrate
            return
            
        api.opus_encoder_ctl(self.encoder, api.OPUS_SET_BITRATE(bitrate))
        self.bitrate = bitrate
    
    def close(self) -> None:
        """Clean up the codec resources."""
        if hasattr(self, 'encoder') and self.encoder:
            api.opus_encoder_destroy(self.encoder)
            self.encoder = None
            
        if hasattr(self, 'decoder') and self.decoder:
            api.opus_decoder_destroy(self.decoder)
            self.decoder = None
            
        self.initialized = False
    
    def __del__(self) -> None:
        """Destructor to clean up resources."""
        self.close() 