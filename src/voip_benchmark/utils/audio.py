"""
Audio Utilities

This module provides utility functions for audio processing.
"""

import os
import wave
import audioop
import numpy as np
from typing import Tuple, Dict, Any, Optional, List


def read_wav_file(file_path: str) -> Tuple[bytes, Dict[str, Any]]:
    """Read audio data from a WAV file.
    
    Args:
        file_path: Path to the WAV file
        
    Returns:
        Tuple of (audio_data, wav_info) where wav_info is a dictionary
        containing the WAV file parameters
        
    Raises:
        ValueError: If the file does not exist or is not a valid WAV file
    """
    if not os.path.exists(file_path):
        raise ValueError(f"File does not exist: {file_path}")
        
    try:
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
    except Exception as e:
        raise ValueError(f"Error reading WAV file: {e}")


def write_wav_file(file_path: str, 
                  audio_data: bytes, 
                  sample_rate: int, 
                  channels: int, 
                  sample_width: int = 2) -> None:
    """Write audio data to a WAV file.
    
    Args:
        file_path: Path to write the WAV file
        audio_data: Raw PCM audio data
        sample_rate: Sample rate in Hz
        channels: Number of audio channels
        sample_width: Sample width in bytes
        
    Raises:
        ValueError: If the parameters are invalid or the file cannot be written
    """
    if not audio_data:
        raise ValueError("No audio data provided")
        
    if sample_rate <= 0:
        raise ValueError(f"Invalid sample rate: {sample_rate}")
        
    if channels <= 0:
        raise ValueError(f"Invalid number of channels: {channels}")
        
    if sample_width not in [1, 2, 3, 4]:
        raise ValueError(f"Invalid sample width: {sample_width}")
    
    try:
        with wave.open(file_path, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)
    except Exception as e:
        raise ValueError(f"Error writing WAV file: {e}")


def convert_sample_rate(audio_data: bytes, 
                       from_rate: int, 
                       to_rate: int, 
                       from_width: int = 2,
                       to_width: Optional[int] = None,
                       from_channels: int = 1,
                       to_channels: Optional[int] = None) -> bytes:
    """Convert sample rate, width, and/or number of channels of audio data.
    
    Args:
        audio_data: Raw PCM audio data
        from_rate: Original sample rate in Hz
        to_rate: Target sample rate in Hz
        from_width: Original sample width in bytes
        to_width: Target sample width in bytes (same as from_width if None)
        from_channels: Original number of channels
        to_channels: Target number of channels (same as from_channels if None)
        
    Returns:
        Converted audio data
        
    Raises:
        ValueError: If the parameters are invalid
    """
    if not audio_data:
        return b''
        
    if from_rate <= 0 or to_rate <= 0:
        raise ValueError(f"Invalid sample rates: {from_rate}, {to_rate}")
        
    if from_width not in [1, 2, 3, 4]:
        raise ValueError(f"Invalid source sample width: {from_width}")
    
    # Set target width and channels to source if not specified
    if to_width is None:
        to_width = from_width
    else:
        if to_width not in [1, 2, 3, 4]:
            raise ValueError(f"Invalid target sample width: {to_width}")
    
    if to_channels is None:
        to_channels = from_channels
    
    # Convert sample rate
    if from_rate != to_rate:
        audio_data = audioop.ratecv(audio_data, from_width, from_channels, from_rate, to_rate, None)[0]
    
    # Convert sample width
    if from_width != to_width:
        audio_data = audioop.lin2lin(audio_data, from_width, to_width)
    
    # Convert number of channels
    if from_channels != to_channels:
        if from_channels == 1 and to_channels == 2:
            # Mono to stereo
            audio_data = audioop.tostereo(audio_data, to_width, 1, 1)
        elif from_channels == 2 and to_channels == 1:
            # Stereo to mono
            audio_data = audioop.tomono(audio_data, from_width, 0.5, 0.5)
        else:
            raise ValueError(f"Unsupported channel conversion: {from_channels} to {to_channels}")
    
    return audio_data


def calculate_rms(audio_data: bytes, sample_width: int = 2) -> float:
    """Calculate the RMS (Root Mean Square) level of audio data.
    
    Args:
        audio_data: Raw PCM audio data
        sample_width: Sample width in bytes
        
    Returns:
        RMS level (0.0 to 1.0)
        
    Raises:
        ValueError: If the sample width is invalid
    """
    if not audio_data:
        return 0.0
        
    if sample_width not in [1, 2, 3, 4]:
        raise ValueError(f"Invalid sample width: {sample_width}")
    
    # Calculate RMS
    rms = audioop.rms(audio_data, sample_width)
    
    # Maximum value based on sample width
    max_value = 2 ** (8 * sample_width - 1)
    
    # Normalize to 0.0 - 1.0
    return rms / max_value


def apply_gain(audio_data: bytes, gain: float, sample_width: int = 2) -> bytes:
    """Apply gain to audio data.
    
    Args:
        audio_data: Raw PCM audio data
        gain: Gain factor (1.0 = no change)
        sample_width: Sample width in bytes
        
    Returns:
        Audio data with gain applied
        
    Raises:
        ValueError: If the sample width is invalid
    """
    if not audio_data:
        return b''
        
    if sample_width not in [1, 2, 3, 4]:
        raise ValueError(f"Invalid sample width: {sample_width}")
    
    # Convert gain to integer factor for audioop
    factor = int(gain * 2 ** 15)
    
    # Apply gain
    return audioop.mul(audio_data, sample_width, factor)


def generate_sine_wave(frequency: float, 
                      duration: float, 
                      sample_rate: int = 48000, 
                      amplitude: float = 0.8,
                      channels: int = 1,
                      sample_width: int = 2) -> bytes:
    """Generate a sine wave.
    
    Args:
        frequency: Frequency in Hz
        duration: Duration in seconds
        sample_rate: Sample rate in Hz
        amplitude: Amplitude (0.0 to 1.0)
        channels: Number of channels
        sample_width: Sample width in bytes
        
    Returns:
        Audio data containing the sine wave
        
    Raises:
        ValueError: If the parameters are invalid
    """
    if frequency <= 0 or duration <= 0 or sample_rate <= 0:
        raise ValueError(f"Invalid parameters: frequency={frequency}, duration={duration}, sample_rate={sample_rate}")
        
    if not 0.0 <= amplitude <= 1.0:
        raise ValueError(f"Invalid amplitude: {amplitude}")
        
    if channels <= 0:
        raise ValueError(f"Invalid number of channels: {channels}")
        
    if sample_width not in [1, 2, 3, 4]:
        raise ValueError(f"Invalid sample width: {sample_width}")
    
    # Maximum value based on sample width
    max_value = 2 ** (8 * sample_width - 1) - 1
    
    # Generate the waveform
    samples = np.arange(int(duration * sample_rate))
    signal = np.sin(2 * np.pi * frequency * samples / sample_rate)
    
    # Apply amplitude
    signal = signal * amplitude * max_value
    
    # Convert to integers based on sample width
    if sample_width == 1:
        signal = signal.astype(np.int8)
    elif sample_width == 2:
        signal = signal.astype(np.int16)
    elif sample_width == 3 or sample_width == 4:
        signal = signal.astype(np.int32)
    
    # Duplicate channels if needed
    if channels > 1:
        signal = np.column_stack([signal] * channels)
    
    # Convert to bytes
    return signal.tobytes()


def mix_audio(audio1: bytes, audio2: bytes, weight1: float = 0.5, weight2: float = 0.5, sample_width: int = 2) -> bytes:
    """Mix two audio streams.
    
    Args:
        audio1: First audio stream
        audio2: Second audio stream
        weight1: Weight of first audio stream (0.0 to 1.0)
        weight2: Weight of second audio stream (0.0 to 1.0)
        sample_width: Sample width in bytes
        
    Returns:
        Mixed audio data
        
    Raises:
        ValueError: If the sample width is invalid or the audio streams have different lengths
    """
    if not audio1 and not audio2:
        return b''
        
    if not audio1:
        return audio2
        
    if not audio2:
        return audio1
        
    if sample_width not in [1, 2, 3, 4]:
        raise ValueError(f"Invalid sample width: {sample_width}")
    
    # Ensure weights are valid
    weight1 = max(0.0, min(1.0, weight1))
    weight2 = max(0.0, min(1.0, weight2))
    
    # Mix audio
    return audioop.add(
        audioop.mul(audio1, sample_width, int(weight1 * 2 ** 15)),
        audioop.mul(audio2, sample_width, int(weight2 * 2 ** 15)),
        sample_width
    )


def audio_to_numpy(audio_data: bytes, sample_width: int = 2, channels: int = 1) -> np.ndarray:
    """Convert audio data to numpy array.
    
    Args:
        audio_data: Raw PCM audio data
        sample_width: Sample width in bytes
        channels: Number of channels
        
    Returns:
        Numpy array containing the audio data
        
    Raises:
        ValueError: If the sample width is invalid
    """
    if not audio_data:
        return np.array([])
        
    if sample_width not in [1, 2, 3, 4]:
        raise ValueError(f"Invalid sample width: {sample_width}")
    
    # Determine dtype based on sample width
    if sample_width == 1:
        dtype = np.int8
    elif sample_width == 2:
        dtype = np.int16
    elif sample_width == 3 or sample_width == 4:
        dtype = np.int32
    
    # Calculate number of samples
    n_samples = len(audio_data) // (sample_width * channels)
    
    # Convert to numpy array
    samples = np.frombuffer(audio_data, dtype=dtype)
    
    # Reshape if multi-channel
    if channels > 1:
        samples = samples.reshape((n_samples, channels))
    
    return samples


def numpy_to_audio(samples: np.ndarray, sample_width: int = 2) -> bytes:
    """Convert numpy array to audio data.
    
    Args:
        samples: Numpy array containing the audio data
        sample_width: Sample width in bytes
        
    Returns:
        Raw PCM audio data
        
    Raises:
        ValueError: If the sample width is invalid
    """
    if len(samples) == 0:
        return b''
        
    if sample_width not in [1, 2, 3, 4]:
        raise ValueError(f"Invalid sample width: {sample_width}")
    
    # Determine dtype based on sample width
    if sample_width == 1:
        samples = samples.astype(np.int8)
    elif sample_width == 2:
        samples = samples.astype(np.int16)
    elif sample_width == 3 or sample_width == 4:
        samples = samples.astype(np.int32)
    
    # Convert to bytes
    return samples.tobytes()


def split_audio_into_frames(audio_data: bytes, frame_size: int, sample_width: int = 2, channels: int = 1) -> List[bytes]:
    """Split audio data into frames.
    
    Args:
        audio_data: Raw PCM audio data
        frame_size: Frame size in samples
        sample_width: Sample width in bytes
        channels: Number of channels
        
    Returns:
        List of audio frames
        
    Raises:
        ValueError: If the sample width is invalid
    """
    if not audio_data:
        return []
        
    if sample_width not in [1, 2, 3, 4]:
        raise ValueError(f"Invalid sample width: {sample_width}")
    
    # Calculate frame size in bytes
    frame_size_bytes = frame_size * sample_width * channels
    
    # Split audio data
    frames = []
    for i in range(0, len(audio_data), frame_size_bytes):
        frame = audio_data[i:i+frame_size_bytes]
        
        # If this is the last frame and it's smaller than the frame size,
        # pad with zeros
        if len(frame) < frame_size_bytes:
            frame += b'\x00' * (frame_size_bytes - len(frame))
            
        frames.append(frame)
    
    return frames 