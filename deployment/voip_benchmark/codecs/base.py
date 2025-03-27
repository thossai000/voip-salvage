"""
Base Codec Definitions

This module defines the base classes and interfaces for all codecs
in the VoIP benchmarking framework.
"""

import abc
import wave
import numpy as np
from typing import Dict, Any, Optional, Tuple


class CodecBase(abc.ABC):
    """Base class for all codec implementations.
    
    This abstract class defines the interface that all codec
    implementations must follow.
    """
    
    def __init__(self, sample_rate: int = 48000, channels: int = 1, **kwargs):
        """Initialize the codec.
        
        Args:
            sample_rate: Audio sample rate in Hz
            channels: Number of audio channels
            **kwargs: Additional codec-specific parameters
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.initialized = False
        self._configure(**kwargs)
        
    @abc.abstractmethod
    def _configure(self, **kwargs) -> None:
        """Configure the codec with specific parameters.
        
        Args:
            **kwargs: Codec-specific parameters
        """
        pass
    
    @abc.abstractmethod
    def encode(self, audio_data: bytes) -> bytes:
        """Encode audio data.
        
        Args:
            audio_data: Raw PCM audio data
            
        Returns:
            Encoded audio data
        """
        pass
    
    @abc.abstractmethod
    def decode(self, encoded_data: bytes) -> bytes:
        """Decode audio data.
        
        Args:
            encoded_data: Encoded audio data
            
        Returns:
            Raw PCM audio data
        """
        pass
    
    @abc.abstractmethod
    def get_bitrate(self) -> int:
        """Get the current bitrate of the codec.
        
        Returns:
            Current bitrate in bits per second
        """
        pass
    
    @abc.abstractmethod
    def set_bitrate(self, bitrate: int) -> None:
        """Set the bitrate of the codec.
        
        Args:
            bitrate: Bitrate in bits per second
        """
        pass
    
    def read_wav_file(self, file_path: str) -> Tuple[bytes, Dict[str, Any]]:
        """Read audio data from a WAV file.
        
        Args:
            file_path: Path to the WAV file
            
        Returns:
            Tuple of (audio_data, wav_info) where wav_info is a dictionary
            containing the WAV file parameters
        """
        with wave.open(file_path, 'rb') as wav_file:
            params = wav_file.getparams()
            wav_info = {
                'channels': params.nchannels,
                'sample_width': params.sampwidth,
                'sample_rate': params.framerate,
                'n_frames': params.nframes,
                'compression_type': params.comptype,
                'compression_name': params.compname
            }
            audio_data = wav_file.readframes(params.nframes)
            
        return audio_data, wav_info
    
    def write_wav_file(self, file_path: str, audio_data: bytes, 
                       sample_rate: Optional[int] = None, 
                       channels: Optional[int] = None,
                       sample_width: int = 2) -> None:
        """Write audio data to a WAV file.
        
        Args:
            file_path: Path to the WAV file
            audio_data: Raw PCM audio data
            sample_rate: Sample rate in Hz (default: self.sample_rate)
            channels: Number of channels (default: self.channels)
            sample_width: Sample width in bytes
        """
        if sample_rate is None:
            sample_rate = self.sample_rate
        if channels is None:
            channels = self.channels
            
        with wave.open(file_path, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)
    
    def get_compression_ratio(self, original_data: bytes, encoded_data: bytes) -> float:
        """Calculate the compression ratio.
        
        Args:
            original_data: Original uncompressed data
            encoded_data: Encoded/compressed data
            
        Returns:
            Compression ratio (encoded_size / original_size)
        """
        if not original_data:
            return 0.0
        return len(encoded_data) / len(original_data)
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(sample_rate={self.sample_rate}, channels={self.channels})" 