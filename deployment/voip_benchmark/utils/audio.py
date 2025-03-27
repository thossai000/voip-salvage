"""
Audio Utilities

This module provides utility functions for handling audio files
and processing audio data for VoIP benchmarking.
"""

import os
import wave
import numpy as np
import subprocess
import tempfile
import logging
from typing import Dict, Any, Tuple, Optional, List, Union

# Default audio parameters
DEFAULT_SAMPLE_RATE = 48000
DEFAULT_SAMPLE_WIDTH = 2  # 16-bit
DEFAULT_CHANNELS = 1      # Mono


def read_wav_file(file_path: str) -> Tuple[bytes, Dict[str, Any]]:
    """Read audio data from a WAV file.
    
    Args:
        file_path: Path to the WAV file
        
    Returns:
        Tuple of (audio_data, wav_info) where wav_info is a dictionary
        containing the WAV file parameters
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        wave.Error: If the file is not a valid WAV file
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"WAV file not found: {file_path}")
        
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
    except wave.Error as e:
        raise wave.Error(f"Invalid WAV file: {e}")


def write_wav_file(file_path: str, 
                  audio_data: bytes, 
                  sample_rate: int = DEFAULT_SAMPLE_RATE,
                  channels: int = DEFAULT_CHANNELS,
                  sample_width: int = DEFAULT_SAMPLE_WIDTH) -> None:
    """Write audio data to a WAV file.
    
    Args:
        file_path: Path to the WAV file to write
        audio_data: Raw PCM audio data
        sample_rate: Sample rate in Hz
        channels: Number of audio channels
        sample_width: Sample width in bytes
        
    Raises:
        IOError: If the file cannot be written
    """
    try:
        with wave.open(file_path, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)
    except IOError as e:
        raise IOError(f"Failed to write WAV file: {e}")


def generate_sine_wave(frequency: float = 440.0, 
                      duration: float = 1.0,
                      sample_rate: int = DEFAULT_SAMPLE_RATE,
                      channels: int = DEFAULT_CHANNELS,
                      sample_width: int = DEFAULT_SAMPLE_WIDTH) -> bytes:
    """Generate a sine wave audio signal.
    
    Args:
        frequency: Frequency of the sine wave in Hz
        duration: Duration of the audio in seconds
        sample_rate: Sample rate in Hz
        channels: Number of audio channels
        sample_width: Sample width in bytes
        
    Returns:
        Raw PCM audio data for the sine wave
    """
    # Generate time array
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # Generate sine wave
    sine_wave = np.sin(2 * np.pi * frequency * t)
    
    # Scale to 16-bit range if sample_width is 2
    if sample_width == 2:
        sine_wave = (sine_wave * 32767).astype(np.int16)
    elif sample_width == 1:
        sine_wave = (sine_wave * 127 + 128).astype(np.uint8)
    elif sample_width == 4:
        sine_wave = (sine_wave * 2147483647).astype(np.int32)
    
    # Duplicate for multiple channels
    if channels > 1:
        sine_wave = np.tile(sine_wave.reshape(-1, 1), (1, channels)).flatten()
    
    # Convert to bytes
    return sine_wave.tobytes()


def convert_wav_format(input_file: str, 
                      output_file: str,
                      target_sample_rate: int = 8000,
                      target_channels: int = 1,
                      target_format: str = "pcm_s16le") -> bool:
    """Convert a WAV file to a different format using ffmpeg.
    
    Args:
        input_file: Path to the input WAV file
        output_file: Path to the output WAV file
        target_sample_rate: Target sample rate in Hz
        target_channels: Target number of channels
        target_format: Target audio format (e.g., "pcm_s16le")
        
    Returns:
        True if conversion was successful, False otherwise
    """
    try:
        cmd = [
            "ffmpeg",
            "-i", input_file,
            "-ar", str(target_sample_rate),
            "-ac", str(target_channels),
            "-acodec", target_format,
            "-y",  # Overwrite output file if it exists
            output_file
        ]
        
        # Run ffmpeg with stdout and stderr captured
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True
        )
        
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"FFmpeg conversion failed: {e.stderr}")
        return False
    except Exception as e:
        logging.error(f"Error converting WAV format: {e}")
        return False


def audio_signal_statistics(audio_data: bytes, 
                           sample_width: int = DEFAULT_SAMPLE_WIDTH, 
                           channels: int = DEFAULT_CHANNELS) -> Dict[str, Any]:
    """Calculate statistics for an audio signal.
    
    Args:
        audio_data: Raw PCM audio data
        sample_width: Sample width in bytes
        channels: Number of audio channels
        
    Returns:
        Dictionary with audio statistics
    """
    # Convert to appropriate numpy array
    if sample_width == 1:
        # 8-bit unsigned PCM
        samples = np.frombuffer(audio_data, dtype=np.uint8)
        # Convert to signed representation
        samples = samples.astype(np.int16) - 128
    elif sample_width == 2:
        # 16-bit signed PCM
        samples = np.frombuffer(audio_data, dtype=np.int16)
    elif sample_width == 4:
        # 32-bit signed PCM
        samples = np.frombuffer(audio_data, dtype=np.int32)
    else:
        raise ValueError(f"Unsupported sample width: {sample_width}")
    
    # Reshape for multi-channel, if needed
    if channels > 1:
        samples = samples.reshape(-1, channels)
    
    # Calculate statistics
    stats = {
        'length': len(audio_data),
        'duration': len(samples) / channels / DEFAULT_SAMPLE_RATE,
        'min': float(np.min(samples)),
        'max': float(np.max(samples)),
        'mean': float(np.mean(samples)),
        'rms': float(np.sqrt(np.mean(samples.astype(np.float64) ** 2))),
        'peak_db': float(20 * np.log10(max(abs(np.max(samples)), abs(np.min(samples))) / (2 ** (8 * sample_width - 1)))),
    }
    
    return stats


def get_wav_file_info(file_path: str) -> Dict[str, Any]:
    """Get information about a WAV file.
    
    Args:
        file_path: Path to the WAV file
        
    Returns:
        Dictionary with WAV file information
        
    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"WAV file not found: {file_path}")
    
    file_size = os.path.getsize(file_path)
    info = {'file_path': file_path, 'file_size': file_size}
    
    try:
        with wave.open(file_path, 'rb') as wav_file:
            params = wav_file.getparams()
            info.update({
                'channels': params.nchannels,
                'sample_width': params.sampwidth,
                'sample_rate': params.framerate,
                'n_frames': params.nframes,
                'compression_type': params.comptype,
                'compression_name': params.compname,
                'duration': params.nframes / params.framerate,
                'bit_depth': params.sampwidth * 8,
                'byte_rate': params.framerate * params.sampwidth * params.nchannels,
                'data_size': params.nframes * params.sampwidth * params.nchannels
            })
    except wave.Error as e:
        # Return partial information if file is not a valid WAV file
        logging.warning(f"Error reading WAV file {file_path}: {e}")
        info.update({
            'error': str(e),
            'valid_wav': False
        })
        return info
        
    return info


def concat_wav_files(input_files: List[str], output_file: str) -> bool:
    """Concatenate multiple WAV files into a single file.
    
    Args:
        input_files: List of input WAV file paths
        output_file: Path to the output WAV file
        
    Returns:
        True if concatenation was successful, False otherwise
        
    Raises:
        ValueError: If no input files are provided or they don't have matching formats
    """
    if not input_files:
        raise ValueError("No input files provided for concatenation")
    
    try:
        # Check if all input files exist
        for file_path in input_files:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"WAV file not found: {file_path}")
        
        # Create temporary file list for ffmpeg
        with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f:
            temp_file = f.name
            for file_path in input_files:
                f.write(f"file '{os.path.abspath(file_path)}'\n")
        
        # Use ffmpeg to concatenate files
        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", temp_file,
            "-c", "copy",
            "-y",  # Overwrite output file if it exists
            output_file
        ]
        
        # Run ffmpeg with stdout and stderr captured
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True
        )
        
        # Remove temporary file
        if os.path.exists(temp_file):
            os.remove(temp_file)
        
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"FFmpeg concatenation failed: {e.stderr}")
        # Remove temporary file
        if 'temp_file' in locals() and os.path.exists(temp_file):
            os.remove(temp_file)
        return False
    except Exception as e:
        logging.error(f"Error concatenating WAV files: {e}")
        # Remove temporary file
        if 'temp_file' in locals() and os.path.exists(temp_file):
            os.remove(temp_file)
        return False 