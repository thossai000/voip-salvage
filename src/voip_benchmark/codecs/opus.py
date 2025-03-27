#!/usr/bin/env python3

import os
import logging
import sys
import ctypes
import wave
import time
import tempfile
import subprocess

try:
    import opuslib
except ImportError:
    logging.warning("opuslib not found. OpusCodec will try to use subprocess with ffmpeg.")
    opuslib = None

class CodecBase:
    """Base class for audio codecs."""
    
    def __init__(self, sample_rate=48000, channels=1):
        """
        Initialize codec with specified parameters.
        
        Args:
            sample_rate: Sample rate in Hz
            channels: Number of audio channels
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.initialized = False
        
    def initialize(self):
        """Initialize the codec. Must be called before encoding/decoding."""
        self.initialized = True
        
    def encode(self, data):
        """
        Encode audio data.
        
        Args:
            data: Raw PCM audio data
            
        Returns:
            Encoded data
        """
        raise NotImplementedError("Subclasses must implement encode()")
        
    def decode(self, data):
        """
        Decode audio data.
        
        Args:
            data: Encoded audio data
            
        Returns:
            Raw PCM audio data
        """
        raise NotImplementedError("Subclasses must implement decode()")
        
    def get_name(self):
        """Get codec name."""
        return "base"


class OpusCodec(CodecBase):
    """Opus audio codec implementation."""
    
    # Application types
    APPLICATION_VOIP = 2048
    APPLICATION_AUDIO = 2049
    APPLICATION_RESTRICTED_LOWDELAY = 2051
    
    # Error codes
    OK = 0
    
    def __init__(self, sample_rate=48000, channels=1, bitrate=24000, 
                 frame_size=20, application=None, complexity=10):
        """
        Initialize Opus codec with specified parameters.
        
        Args:
            sample_rate: Sample rate in Hz (8000, 12000, 16000, 24000, or 48000)
            channels: Number of audio channels (1 or 2)
            bitrate: Target bitrate in bps (default: 24000)
            frame_size: Frame size in milliseconds (2.5, 5, 10, 20, 40, 60, 80, 100, 120)
            application: Application type (VOIP, AUDIO, or RESTRICTED_LOWDELAY)
            complexity: Encoding complexity (0-10, higher is more complex but better quality)
        """
        super().__init__(sample_rate, channels)
        
        # Validate sample rate
        valid_sample_rates = [8000, 12000, 16000, 24000, 48000]
        if sample_rate not in valid_sample_rates:
            logging.warning(f"Sample rate {sample_rate} not optimal for Opus. "
                          f"Using closest valid rate.")
            # Find closest valid rate
            self.sample_rate = min(valid_sample_rates, 
                                  key=lambda x: abs(x - sample_rate))
        
        # Validate channels
        if channels not in [1, 2]:
            logging.warning(f"Channels must be 1 or 2 for Opus. Using 1 channel.")
            self.channels = 1
            
        # Set application type
        if application is None:
            self.application = self.APPLICATION_VOIP
        else:
            self.application = application
            
        self.bitrate = bitrate
        self.frame_size_ms = frame_size
        self.complexity = min(10, max(0, complexity))
        
        # Calculate frame size in samples
        self.frame_size = int(self.sample_rate * self.frame_size_ms / 1000)
        
        # Opus encoder/decoder objects
        self.encoder = None
        self.decoder = None
        
        # For fallback implementation
        self.use_ffmpeg = opuslib is None
        self.temp_dir = None
        
    def initialize(self):
        """Initialize Opus encoder and decoder."""
        if self.initialized:
            return
            
        if not self.use_ffmpeg:
            try:
                # Initialize with opuslib
                self.encoder = opuslib.Encoder(
                    self.sample_rate,
                    self.channels,
                    self.application
                )
                
                # Set encoder parameters
                self.encoder.bitrate = self.bitrate
                self.encoder.complexity = self.complexity
                
                self.decoder = opuslib.Decoder(
                    self.sample_rate,
                    self.channels
                )
                
                self.initialized = True
                
            except Exception as e:
                logging.error(f"Failed to initialize Opus codec with opuslib: {e}")
                self.use_ffmpeg = True
                
        if self.use_ffmpeg:
            # Check if ffmpeg is available
            try:
                result = subprocess.run(
                    ["ffmpeg", "-version"], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE
                )
                if result.returncode != 0:
                    raise RuntimeError("ffmpeg not found")
                    
                # Create temp directory for intermediate files
                self.temp_dir = tempfile.mkdtemp(prefix="opus_codec_")
                self.initialized = True
                
            except Exception as e:
                logging.error(f"Failed to initialize ffmpeg fallback: {e}")
                raise RuntimeError("Failed to initialize Opus codec") from e
                
    def encode(self, data):
        """
        Encode PCM audio data to Opus.
        
        Args:
            data: Raw PCM audio data (bytes)
            
        Returns:
            Opus encoded data (bytes)
        """
        if not self.initialized:
            self.initialize()
            
        if not self.use_ffmpeg:
            # Use opuslib
            try:
                return self.encoder.encode(data, self.frame_size)
            except Exception as e:
                logging.error(f"Opus encoding error: {e}")
                return b''
        else:
            # Use ffmpeg
            try:
                # Create temporary input and output files
                in_file = os.path.join(self.temp_dir, f"in_{time.time()}.pcm")
                out_file = os.path.join(self.temp_dir, f"out_{time.time()}.opus")
                
                # Write raw PCM to input file
                with open(in_file, 'wb') as f:
                    f.write(data)
                
                # Run ffmpeg to encode
                cmd = [
                    "ffmpeg", "-y",
                    "-f", "s16le",  # 16-bit PCM
                    "-ar", str(self.sample_rate),
                    "-ac", str(self.channels),
                    "-i", in_file,
                    "-c:a", "libopus",
                    "-b:a", f"{self.bitrate}",
                    "-application", "voip" if self.application == self.APPLICATION_VOIP else "audio",
                    "-compression_level", str(self.complexity),
                    "-frame_duration", str(self.frame_size_ms),
                    out_file
                ]
                
                result = subprocess.run(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE
                )
                
                if result.returncode != 0:
                    raise RuntimeError(f"ffmpeg encoding failed: {result.stderr.decode()}")
                
                # Read encoded data
                with open(out_file, 'rb') as f:
                    encoded_data = f.read()
                
                # Clean up temporary files
                try:
                    os.remove(in_file)
                    os.remove(out_file)
                except:
                    pass
                
                return encoded_data
                
            except Exception as e:
                logging.error(f"ffmpeg encoding error: {e}")
                return b''
            
    def decode(self, data):
        """
        Decode Opus audio data to PCM.
        
        Args:
            data: Opus encoded data (bytes)
            
        Returns:
            Raw PCM audio data (bytes)
        """
        if not self.initialized:
            self.initialize()
            
        if not self.use_ffmpeg:
            # Use opuslib
            try:
                return self.decoder.decode(data, self.frame_size)
            except Exception as e:
                logging.error(f"Opus decoding error: {e}")
                return b''
        else:
            # Use ffmpeg
            try:
                # Create temporary input and output files
                in_file = os.path.join(self.temp_dir, f"in_{time.time()}.opus")
                out_file = os.path.join(self.temp_dir, f"out_{time.time()}.pcm")
                
                # Write encoded data to input file
                with open(in_file, 'wb') as f:
                    f.write(data)
                
                # Run ffmpeg to decode
                cmd = [
                    "ffmpeg", "-y",
                    "-i", in_file,
                    "-f", "s16le",  # 16-bit PCM
                    "-ar", str(self.sample_rate),
                    "-ac", str(self.channels),
                    out_file
                ]
                
                result = subprocess.run(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE
                )
                
                if result.returncode != 0:
                    raise RuntimeError(f"ffmpeg decoding failed: {result.stderr.decode()}")
                
                # Read decoded data
                with open(out_file, 'rb') as f:
                    decoded_data = f.read()
                
                # Clean up temporary files
                try:
                    os.remove(in_file)
                    os.remove(out_file)
                except:
                    pass
                
                return decoded_data
                
            except Exception as e:
                logging.error(f"ffmpeg decoding error: {e}")
                return b''
    
    def cleanup(self):
        """Clean up resources."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                import shutil
                shutil.rmtree(self.temp_dir)
            except:
                pass
                
    def get_name(self):
        """Get codec name."""
        return "opus"


def create_opus_wav(input_wav, output_wav, bitrate=24000, complexity=10):
    """
    Create a new WAV file encoded with Opus.
    
    Args:
        input_wav: Path to input WAV file
        output_wav: Path to output WAV file
        bitrate: Opus bitrate in bps
        complexity: Opus encoding complexity (0-10)
        
    Returns:
        Tuple of (input_size, output_size, compression_ratio)
    """
    try:
        # Open input WAV file
        wav_in = wave.open(input_wav, 'rb')
        sample_rate = wav_in.getframerate()
        channels = wav_in.getnchannels()
        sample_width = wav_in.getsampwidth()
        
        # Create Opus codec
        codec = OpusCodec(
            sample_rate=sample_rate,
            channels=channels,
            bitrate=bitrate,
            complexity=complexity
        )
        codec.initialize()
        
        # Create output WAV file
        wav_out = wave.open(output_wav, 'wb')
        wav_out.setnchannels(channels)
        wav_out.setsampwidth(sample_width)
        wav_out.setframerate(sample_rate)
        
        # Process audio in chunks
        chunk_size = int(sample_rate * 20 / 1000)  # 20ms chunks
        
        encoded_size = 0
        
        data = wav_in.readframes(chunk_size)
        while data:
            # Encode and decode with Opus
            encoded = codec.encode(data)
            encoded_size += len(encoded)
            
            decoded = codec.decode(encoded)
            wav_out.writeframes(decoded)
            
            data = wav_in.readframes(chunk_size)
        
        wav_in.close()
        wav_out.close()
        
        # Calculate statistics
        input_size = os.path.getsize(input_wav)
        output_size = os.path.getsize(output_wav)
        compression_ratio = encoded_size / input_size if input_size > 0 else 0
        
        return (input_size, output_size, compression_ratio)
        
    except Exception as e:
        logging.error(f"Error creating Opus WAV: {e}")
        return (0, 0, 0)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Opus codec utilities")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Create command for converting WAV to Opus WAV
    convert_parser = subparsers.add_parser("convert", help="Convert WAV to Opus WAV")
    convert_parser.add_argument("input", help="Input WAV file")
    convert_parser.add_argument("output", help="Output WAV file")
    convert_parser.add_argument("--bitrate", type=int, default=24000, 
                               help="Opus bitrate in bps")
    convert_parser.add_argument("--complexity", type=int, default=10, 
                               help="Opus encoding complexity (0-10)")
    
    args = parser.parse_args()
    
    if args.command == "convert":
        input_size, output_size, compression_ratio = create_opus_wav(
            args.input, args.output, args.bitrate, args.complexity
        )
        
        print(f"Input size: {input_size} bytes")
        print(f"Output size: {output_size} bytes")
        print(f"Compression ratio: {compression_ratio:.3f}")
        print(f"Bandwidth savings: {(1 - compression_ratio) * 100:.1f}%") 