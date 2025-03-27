#!/usr/bin/env python3

import os
import subprocess
import logging
import numpy as np
import wave
import tempfile
from scipy.io import wavfile
import soundfile as sf

class AudioUtils:
    """
    Utility functions for audio processing.
    """
    
    @staticmethod
    def convert_to_wav(input_file, output_file=None, sample_rate=16000, channels=1):
        """
        Convert any audio file to WAV format.
        
        Args:
            input_file: Path to input audio file
            output_file: Path to output WAV file (if None, creates temp file)
            sample_rate: Target sample rate
            channels: Target number of channels
            
        Returns:
            Path to output WAV file
        """
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file not found: {input_file}")
            
        # If no output file specified, create temp file
        if output_file is None:
            fd, output_file = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            
        # Use ffmpeg for conversion
        try:
            cmd = [
                "ffmpeg",
                "-i", input_file,
                "-ar", str(sample_rate),
                "-ac", str(channels),
                "-y",  # Overwrite output file if it exists
                output_file
            ]
            
            # Run ffmpeg and capture output
            process = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            if process.returncode != 0:
                logging.error(f"Error converting audio: {process.stderr}")
                raise RuntimeError(f"FFmpeg conversion failed: {process.stderr}")
                
            return output_file
            
        except Exception as e:
            logging.error(f"Error converting audio: {str(e)}")
            raise
            
    @staticmethod
    def create_silence(duration, output_file, sample_rate=16000, channels=1):
        """
        Create a silent WAV file.
        
        Args:
            duration: Duration in seconds
            output_file: Path to output WAV file
            sample_rate: Sample rate in Hz
            channels: Number of channels
            
        Returns:
            Path to output WAV file
        """
        # Calculate number of frames
        num_frames = int(duration * sample_rate)
        
        # Create silence array
        silence = np.zeros(num_frames, dtype=np.int16)
        
        # Write silence to WAV file
        with wave.open(output_file, 'wb') as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(2)  # 16-bit samples
            wav.setframerate(sample_rate)
            wav.writeframes(silence.tobytes())
            
        return output_file
        
    @staticmethod
    def trim_audio(input_file, output_file, start_sec=0, duration_sec=None):
        """
        Trim audio file to specified duration.
        
        Args:
            input_file: Path to input audio file
            output_file: Path to output audio file
            start_sec: Start time in seconds
            duration_sec: Duration in seconds (None for end of file)
            
        Returns:
            Path to output audio file
        """
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file not found: {input_file}")
            
        # Build ffmpeg command
        cmd = ["ffmpeg", "-i", input_file]
        
        # Add trim options
        cmd.extend(["-ss", str(start_sec)])
        
        if duration_sec is not None:
            cmd.extend(["-t", str(duration_sec)])
            
        # Add output file
        cmd.extend(["-y", output_file])
        
        # Run ffmpeg
        try:
            process = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            if process.returncode != 0:
                logging.error(f"Error trimming audio: {process.stderr}")
                raise RuntimeError(f"FFmpeg trim failed: {process.stderr}")
                
            return output_file
            
        except Exception as e:
            logging.error(f"Error trimming audio: {str(e)}")
            raise
            
    @staticmethod
    def concatenate_audio(input_files, output_file):
        """
        Concatenate multiple audio files.
        
        Args:
            input_files: List of input audio files
            output_file: Path to output audio file
            
        Returns:
            Path to output audio file
        """
        # Check input files
        for file in input_files:
            if not os.path.exists(file):
                raise FileNotFoundError(f"Input file not found: {file}")
                
        # Create temporary file list
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp:
            for file in input_files:
                temp.write(f"file '{os.path.abspath(file)}'\n")
            temp_file = temp.name
            
        try:
            # Use ffmpeg concat demuxer
            cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", temp_file,
                "-c", "copy",
                "-y",
                output_file
            ]
            
            # Run ffmpeg
            process = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            if process.returncode != 0:
                logging.error(f"Error concatenating audio: {process.stderr}")
                raise RuntimeError(f"FFmpeg concat failed: {process.stderr}")
                
            return output_file
            
        except Exception as e:
            logging.error(f"Error concatenating audio: {str(e)}")
            raise
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file):
                os.unlink(temp_file)
                
    @staticmethod
    def apply_gain(input_file, output_file, gain_db):
        """
        Apply gain to audio file.
        
        Args:
            input_file: Path to input audio file
            output_file: Path to output audio file
            gain_db: Gain in decibels (positive or negative)
            
        Returns:
            Path to output audio file
        """
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file not found: {input_file}")
            
        # Use ffmpeg with volume filter
        cmd = [
            "ffmpeg",
            "-i", input_file,
            "-af", f"volume={gain_db}dB",
            "-y",
            output_file
        ]
        
        try:
            process = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            if process.returncode != 0:
                logging.error(f"Error applying gain: {process.stderr}")
                raise RuntimeError(f"FFmpeg volume filter failed: {process.stderr}")
                
            return output_file
            
        except Exception as e:
            logging.error(f"Error applying gain: {str(e)}")
            raise
            
    @staticmethod
    def add_noise(input_file, output_file, noise_level=0.01):
        """
        Add white noise to audio file.
        
        Args:
            input_file: Path to input audio file
            output_file: Path to output audio file
            noise_level: Noise level (0.0 to 1.0)
            
        Returns:
            Path to output audio file
        """
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file not found: {input_file}")
            
        try:
            # Read audio file
            sample_rate, audio = wavfile.read(input_file)
            
            # Generate noise
            noise = np.random.normal(0, noise_level * np.max(np.abs(audio)), audio.shape)
            
            # Add noise to audio
            noisy_audio = audio + noise.astype(audio.dtype)
            
            # Write output file
            wavfile.write(output_file, sample_rate, noisy_audio)
            
            return output_file
            
        except Exception as e:
            logging.error(f"Error adding noise: {str(e)}")
            raise
            
    @staticmethod
    def get_audio_info(audio_file):
        """
        Get information about an audio file.
        
        Args:
            audio_file: Path to audio file
            
        Returns:
            Dictionary with audio information
        """
        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"Audio file not found: {audio_file}")
            
        try:
            info = {}
            info["file_size"] = os.path.getsize(audio_file)
            
            # Use soundfile for more comprehensive format support
            sf_info = sf.info(audio_file)
            info["sample_rate"] = sf_info.samplerate
            info["channels"] = sf_info.channels
            info["duration"] = sf_info.duration
            info["format"] = sf_info.format
            
            # Try to get more detailed wave info if it's a wav file
            try:
                with wave.open(audio_file, 'rb') as wav:
                    info["sample_width"] = wav.getsampwidth()
                    info["compression_type"] = wav.getcomptype()
                    info["compression_name"] = wav.getcompname()
            except:
                # Not a valid wave file or not accessible - continue with what we have
                pass
            
            return info
            
        except Exception as e:
            logging.error(f"Error getting audio info: {str(e)}")
            raise
            
    @staticmethod
    def generate_tone(output_file, frequency=1000, duration=1.0, sample_rate=16000, amplitude=0.5):
        """
        Generate a sine wave tone.
        
        Args:
            output_file: Path to output WAV file
            frequency: Tone frequency in Hz
            duration: Duration in seconds
            sample_rate: Sample rate in Hz
            amplitude: Amplitude (0.0 to 1.0)
            
        Returns:
            Path to output WAV file
        """
        # Generate time array
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        
        # Generate sine wave
        tone = amplitude * np.sin(2 * np.pi * frequency * t)
        
        # Convert to 16-bit PCM
        tone_int16 = (tone * 32767).astype(np.int16)
        
        # Write to WAV file
        wavfile.write(output_file, sample_rate, tone_int16)
        
        return output_file
        
    @staticmethod
    def generate_dtmf(output_file, digits="1234", digit_duration=0.1, gap_duration=0.1):
        """
        Generate DTMF tones for given digits.
        
        Args:
            output_file: Path to output WAV file
            digits: String of DTMF digits (0-9, A-D, *, #)
            digit_duration: Duration of each digit in seconds
            gap_duration: Duration of gap between digits in seconds
            
        Returns:
            Path to output WAV file
        """
        # DTMF frequency pairs (low, high)
        dtmf_freqs = {
            '1': (697, 1209),
            '2': (697, 1336),
            '3': (697, 1477),
            'A': (697, 1633),
            '4': (770, 1209),
            '5': (770, 1336),
            '6': (770, 1477),
            'B': (770, 1633),
            '7': (852, 1209),
            '8': (852, 1336),
            '9': (852, 1477),
            'C': (852, 1633),
            '*': (941, 1209),
            '0': (941, 1336),
            '#': (941, 1477),
            'D': (941, 1633)
        }
        
        sample_rate = 8000  # Standard DTMF sample rate
        
        # Create empty audio buffer
        total_duration = len(digits) * (digit_duration + gap_duration) - gap_duration
        audio = np.zeros(int(total_duration * sample_rate))
        
        # Generate each DTMF tone
        for i, digit in enumerate(digits):
            if digit in dtmf_freqs:
                # Calculate start and end sample indices
                start_idx = int(i * (digit_duration + gap_duration) * sample_rate)
                end_idx = int(start_idx + digit_duration * sample_rate)
                
                # Generate time array for this digit
                t = np.linspace(0, digit_duration, int(digit_duration * sample_rate), False)
                
                # Get DTMF frequencies
                low_freq, high_freq = dtmf_freqs[digit]
                
                # Generate tones (sum of two frequencies)
                tone = 0.5 * np.sin(2 * np.pi * low_freq * t) + 0.5 * np.sin(2 * np.pi * high_freq * t)
                
                # Apply envelope to avoid clicks
                envelope = np.ones_like(tone)
                ramp_samples = int(0.01 * sample_rate)  # 10ms ramp
                envelope[:ramp_samples] = np.linspace(0, 1, ramp_samples)
                envelope[-ramp_samples:] = np.linspace(1, 0, ramp_samples)
                
                # Apply envelope
                tone = tone * envelope
                
                # Add to audio buffer
                audio[start_idx:end_idx] = tone
        
        # Normalize and convert to 16-bit PCM
        audio = audio / np.max(np.abs(audio))
        audio_int16 = (audio * 32767).astype(np.int16)
        
        # Write to WAV file
        wavfile.write(output_file, sample_rate, audio_int16)
        
        return output_file
        
    @staticmethod
    def mix_audio_files(input_files, output_file, weights=None):
        """
        Mix multiple audio files into one.
        
        Args:
            input_files: List of input audio files
            output_file: Path to output audio file
            weights: List of weights for each input file (None for equal weights)
            
        Returns:
            Path to output audio file
        """
        if weights is None:
            weights = [1.0] * len(input_files)
            
        if len(weights) != len(input_files):
            raise ValueError("Number of weights must match number of input files")
            
        # Check input files
        for file in input_files:
            if not os.path.exists(file):
                raise FileNotFoundError(f"Input file not found: {file}")
                
        # Convert all to same format first
        temp_files = []
        sample_rate = None
        max_duration = 0
        
        try:
            # Convert files to same format and get max duration
            for file in input_files:
                info = AudioUtils.get_audio_info(file)
                if sample_rate is None:
                    sample_rate = info["sample_rate"]
                    
                max_duration = max(max_duration, info["duration"])
                
                # Convert to temporary file with consistent format
                fd, temp_file = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                AudioUtils.convert_to_wav(file, temp_file, sample_rate=sample_rate)
                temp_files.append(temp_file)
                
            # Read all audio files
            audio_data = []
            for temp_file in temp_files:
                sr, data = wavfile.read(temp_file)
                audio_data.append(data)
                
            # Normalize lengths (pad with zeros)
            max_samples = int(max_duration * sample_rate)
            for i in range(len(audio_data)):
                if len(audio_data[i]) < max_samples:
                    padding = np.zeros(max_samples - len(audio_data[i]), dtype=audio_data[i].dtype)
                    audio_data[i] = np.concatenate([audio_data[i], padding])
                elif len(audio_data[i]) > max_samples:
                    audio_data[i] = audio_data[i][:max_samples]
                    
            # Mix audio
            mixed = np.zeros(max_samples, dtype=np.float32)
            for data, weight in zip(audio_data, weights):
                mixed += weight * data.astype(np.float32) / 32767.0
                
            # Normalize to prevent clipping
            if np.max(np.abs(mixed)) > 1.0:
                mixed = mixed / np.max(np.abs(mixed))
                
            # Convert back to int16
            mixed_int16 = (mixed * 32767).astype(np.int16)
            
            # Write to output file
            wavfile.write(output_file, sample_rate, mixed_int16)
            
            return output_file
            
        except Exception as e:
            logging.error(f"Error mixing audio: {str(e)}")
            raise
        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Audio utilities")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Convert command
    convert_parser = subparsers.add_parser("convert", help="Convert audio to WAV")
    convert_parser.add_argument("input", help="Input audio file")
    convert_parser.add_argument("output", help="Output WAV file")
    convert_parser.add_argument("--rate", type=int, default=16000, help="Sample rate")
    convert_parser.add_argument("--channels", type=int, default=1, help="Channels")
    
    # Info command
    info_parser = subparsers.add_parser("info", help="Get audio file info")
    info_parser.add_argument("file", help="Audio file")
    
    # Generate tone command
    tone_parser = subparsers.add_parser("tone", help="Generate tone")
    tone_parser.add_argument("output", help="Output WAV file")
    tone_parser.add_argument("--freq", type=float, default=1000, help="Frequency in Hz")
    tone_parser.add_argument("--duration", type=float, default=1.0, help="Duration in seconds")
    
    # Mix command
    mix_parser = subparsers.add_parser("mix", help="Mix audio files")
    mix_parser.add_argument("inputs", nargs="+", help="Input audio files")
    mix_parser.add_argument("output", help="Output WAV file")
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(levelname)s - %(message)s')
    
    if args.command == "convert":
        output_file = AudioUtils.convert_to_wav(
            args.input, 
            args.output, 
            sample_rate=args.rate, 
            channels=args.channels
        )
        print(f"Converted audio saved to {output_file}")
        
    elif args.command == "info":
        info = AudioUtils.get_audio_info(args.file)
        print("\nAudio File Information:")
        print("-" * 40)
        for key, value in info.items():
            print(f"{key}: {value}")
            
    elif args.command == "tone":
        output_file = AudioUtils.generate_tone(
            args.output,
            frequency=args.freq,
            duration=args.duration
        )
        print(f"Tone generated and saved to {output_file}")
        
    elif args.command == "mix":
        output_file = AudioUtils.mix_audio_files(
            args.inputs[:-1],  # All but the last argument are input files
            args.inputs[-1]    # Last argument is output file
        )
        print(f"Mixed audio saved to {output_file}") 