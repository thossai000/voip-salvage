#!/usr/bin/env python3

import os
import json
import numpy as np
import wave
import logging
from collections import defaultdict
from datetime import datetime

class VoIPMetrics:
    """
    Calculate and report metrics for VoIP benchmark tests.
    """
    
    def __init__(self, results_dir="results"):
        """
        Initialize VoIP metrics calculator.
        
        Args:
            results_dir: Directory to store results
        """
        self.results_dir = results_dir
        os.makedirs(results_dir, exist_ok=True)
        
        # Metrics storage
        self.metrics = defaultdict(dict)
        self.test_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def calculate_audio_metrics(self, original_file, received_file):
        """
        Calculate audio metrics between original and received files.
        
        Args:
            original_file: Path to original audio file
            received_file: Path to received audio file
            
        Returns:
            Dictionary of audio metrics
        """
        metrics = {}
        
        # Check if files exist
        if not os.path.exists(original_file):
            logging.error(f"Original file not found: {original_file}")
            return {"error": "Original file not found"}
            
        if not os.path.exists(received_file):
            logging.error(f"Received file not found: {received_file}")
            return {"error": "Received file not found"}
        
        # Get file sizes
        original_size = os.path.getsize(original_file)
        received_size = os.path.getsize(received_file)
        
        metrics["original_size_bytes"] = original_size
        metrics["received_size_bytes"] = received_size
        metrics["size_ratio"] = received_size / original_size if original_size > 0 else 0
        
        # Extract audio data if WAV files
        try:
            with wave.open(original_file, 'rb') as orig_wav:
                orig_params = orig_wav.getparams()
                orig_frames = orig_wav.readframes(orig_wav.getnframes())
                orig_audio = np.frombuffer(orig_frames, dtype=np.int16)
                
            with wave.open(received_file, 'rb') as recv_wav:
                recv_params = recv_wav.getparams()
                recv_frames = recv_wav.readframes(recv_wav.getnframes())
                recv_audio = np.frombuffer(recv_frames, dtype=np.int16)
                
            # Calculate audio metrics if both are valid WAV files
            metrics["original_duration_sec"] = orig_wav.getnframes() / orig_wav.getframerate()
            metrics["received_duration_sec"] = recv_wav.getnframes() / recv_wav.getframerate()
            
            # Calculate RMS energy
            if len(orig_audio) > 0:
                orig_rms = np.sqrt(np.mean(np.square(orig_audio.astype(np.float32))))
                metrics["original_rms"] = float(orig_rms)
                
            if len(recv_audio) > 0:
                recv_rms = np.sqrt(np.mean(np.square(recv_audio.astype(np.float32))))
                metrics["received_rms"] = float(recv_rms)
            
            # Calculate signal-to-noise ratio if possible (simplified)
            if len(orig_audio) > 0 and len(recv_audio) > 0:
                # Truncate to same length for comparison
                min_len = min(len(orig_audio), len(recv_audio))
                orig_audio = orig_audio[:min_len]
                recv_audio = recv_audio[:min_len]
                
                # Calculate signal energy
                signal_power = np.mean(np.square(orig_audio.astype(np.float32)))
                
                # Calculate noise (difference between original and received)
                noise = orig_audio.astype(np.float32) - recv_audio.astype(np.float32)
                noise_power = np.mean(np.square(noise))
                
                # Calculate SNR
                if noise_power > 0:
                    snr = 10 * np.log10(signal_power / noise_power)
                    metrics["snr_db"] = float(snr)
                
        except Exception as e:
            logging.warning(f"Could not calculate detailed audio metrics: {str(e)}")
            
        return metrics
        
    def calculate_network_metrics(self, packet_stats):
        """
        Calculate network metrics from packet statistics.
        
        Args:
            packet_stats: Dictionary with packet statistics
            
        Returns:
            Dictionary of network metrics
        """
        metrics = {}
        
        # Basic statistics
        metrics["packet_count"] = packet_stats.get("packet_count", 0)
        metrics["bytes_sent"] = packet_stats.get("bytes_sent", 0)
        metrics["bytes_received"] = packet_stats.get("bytes_received", 0)
        
        # Calculate packet loss
        sent = packet_stats.get("packet_count_sent", 0)
        received = packet_stats.get("packet_count_received", 0)
        
        if sent > 0:
            packet_loss = 1.0 - (received / sent)
            metrics["packet_loss"] = packet_loss
            
        # Add timing metrics
        metrics["duration_sec"] = packet_stats.get("duration_sec", 0)
        
        if metrics["duration_sec"] > 0:
            # Calculate bitrate
            bytes_received = metrics["bytes_received"]
            bitrate_bps = (bytes_received * 8) / metrics["duration_sec"]
            metrics["bitrate_bps"] = bitrate_bps
            
        # Add jitter if available
        if "jitter_ms" in packet_stats:
            metrics["jitter_ms"] = packet_stats["jitter_ms"]
            
        # Add round-trip time if available
        if "rtt_ms" in packet_stats:
            metrics["rtt_ms"] = packet_stats["rtt_ms"]
        
        return metrics
        
    def calculate_codec_metrics(self, codec_name, bitrate, original_size, compressed_size):
        """
        Calculate codec performance metrics.
        
        Args:
            codec_name: Name of the codec
            bitrate: Codec bitrate in bps
            original_size: Size of original audio in bytes
            compressed_size: Size of compressed audio in bytes
            
        Returns:
            Dictionary of codec metrics
        """
        metrics = {
            "codec_name": codec_name,
            "bitrate_bps": bitrate,
            "original_size_bytes": original_size,
            "compressed_size_bytes": compressed_size,
        }
        
        # Calculate compression ratio
        if original_size > 0:
            metrics["compression_ratio"] = compressed_size / original_size
            metrics["compression_percent"] = (1 - (compressed_size / original_size)) * 100
            
        return metrics
        
    def add_test_metrics(self, test_name, metrics_dict):
        """
        Add metrics for a specific test.
        
        Args:
            test_name: Name of the test
            metrics_dict: Dictionary with metrics
        """
        self.metrics[test_name] = metrics_dict
        
    def save_metrics(self, filename=None):
        """
        Save metrics to a JSON file.
        
        Args:
            filename: Optional filename, will use test_id if not provided
            
        Returns:
            Path to saved file
        """
        if filename is None:
            filename = f"metrics_{self.test_id}.json"
            
        filepath = os.path.join(self.results_dir, filename)
        
        # Add timestamp
        results = {
            "timestamp": datetime.now().isoformat(),
            "test_id": self.test_id,
            "metrics": dict(self.metrics)
        }
        
        # Save to JSON file
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)
            
        logging.info(f"Metrics saved to {filepath}")
        
        return filepath
        
    def generate_report(self, output_file=None):
        """
        Generate a human-readable report from metrics.
        
        Args:
            output_file: Optional output file path
            
        Returns:
            Report as string and saves to file if output_file is provided
        """
        if not self.metrics:
            return "No metrics available"
            
        report = []
        report.append("=" * 60)
        report.append(f"VoIP Benchmark Report - {self.test_id}")
        report.append("=" * 60)
        report.append("")
        
        # Process each test
        for test_name, metrics in self.metrics.items():
            report.append(f"Test: {test_name}")
            report.append("-" * 40)
            
            # Audio metrics
            if any(k in metrics for k in ["original_size_bytes", "received_size_bytes"]):
                report.append("Audio Metrics:")
                if "original_size_bytes" in metrics:
                    report.append(f"  Original Size: {metrics['original_size_bytes']:,} bytes")
                if "received_size_bytes" in metrics:
                    report.append(f"  Received Size: {metrics['received_size_bytes']:,} bytes")
                if "size_ratio" in metrics:
                    report.append(f"  Size Ratio: {metrics['size_ratio']:.2f}")
                if "original_duration_sec" in metrics:
                    report.append(f"  Original Duration: {metrics['original_duration_sec']:.2f} sec")
                if "received_duration_sec" in metrics:
                    report.append(f"  Received Duration: {metrics['received_duration_sec']:.2f} sec")
                if "snr_db" in metrics:
                    report.append(f"  Signal-to-Noise Ratio: {metrics['snr_db']:.2f} dB")
                report.append("")
                
            # Network metrics
            if any(k in metrics for k in ["packet_count", "bytes_sent", "packet_loss"]):
                report.append("Network Metrics:")
                if "packet_count" in metrics:
                    report.append(f"  Packet Count: {metrics['packet_count']:,}")
                if "bytes_sent" in metrics:
                    report.append(f"  Bytes Sent: {metrics['bytes_sent']:,}")
                if "bytes_received" in metrics:
                    report.append(f"  Bytes Received: {metrics['bytes_received']:,}")
                if "packet_loss" in metrics:
                    report.append(f"  Packet Loss: {metrics['packet_loss']:.2%}")
                if "bitrate_bps" in metrics:
                    report.append(f"  Bitrate: {metrics['bitrate_bps']/1000:.2f} kbps")
                if "jitter_ms" in metrics:
                    report.append(f"  Jitter: {metrics['jitter_ms']:.2f} ms")
                if "rtt_ms" in metrics:
                    report.append(f"  Round-Trip Time: {metrics['rtt_ms']:.2f} ms")
                report.append("")
                
            # Codec metrics
            if any(k in metrics for k in ["codec_name", "compression_ratio"]):
                report.append("Codec Metrics:")
                if "codec_name" in metrics:
                    report.append(f"  Codec: {metrics['codec_name']}")
                if "bitrate_bps" in metrics:
                    report.append(f"  Bitrate: {metrics['bitrate_bps']/1000:.2f} kbps")
                if "compression_ratio" in metrics:
                    report.append(f"  Compression Ratio: {metrics['compression_ratio']:.4f}")
                if "compression_percent" in metrics:
                    report.append(f"  Compression: {metrics['compression_percent']:.2f}%")
                report.append("")
                
            # Add any other metrics
            other_metrics = {k: v for k, v in metrics.items() 
                            if k not in ["original_size_bytes", "received_size_bytes", 
                                        "size_ratio", "original_duration_sec", 
                                        "received_duration_sec", "snr_db",
                                        "packet_count", "bytes_sent", "bytes_received",
                                        "packet_loss", "bitrate_bps", "jitter_ms", "rtt_ms",
                                        "codec_name", "compression_ratio", "compression_percent"]}
            
            if other_metrics:
                report.append("Other Metrics:")
                for key, value in sorted(other_metrics.items()):
                    report.append(f"  {key}: {value}")
                report.append("")
                
            report.append("")
            
        report_text = "\n".join(report)
        
        # Save to file if requested
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_text)
            logging.info(f"Report saved to {output_file}")
            
        return report_text


def get_audio_duration(audio_file):
    """
    Get the duration of an audio file in seconds.
    
    Args:
        audio_file: Path to WAV file
        
    Returns:
        Duration in seconds or None if not a valid WAV file
    """
    try:
        with wave.open(audio_file, 'rb') as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            duration = frames / rate
            return duration
    except Exception as e:
        logging.error(f"Error getting audio duration: {str(e)}")
        return None


def compare_audio_files(file1, file2):
    """
    Compare two audio files and return differences.
    
    Args:
        file1: Path to first audio file
        file2: Path to second audio file
        
    Returns:
        Dictionary with comparison metrics
    """
    metrics = {}
    
    # Check file existence
    if not os.path.exists(file1):
        return {"error": f"File not found: {file1}"}
        
    if not os.path.exists(file2):
        return {"error": f"File not found: {file2}"}
        
    # Get file sizes
    size1 = os.path.getsize(file1)
    size2 = os.path.getsize(file2)
    
    metrics["file1_size"] = size1
    metrics["file2_size"] = size2
    metrics["size_diff_bytes"] = size2 - size1
    metrics["size_ratio"] = size2 / size1 if size1 > 0 else 0
    
    # Compare WAV parameters if both are WAV files
    try:
        with wave.open(file1, 'rb') as wav1, wave.open(file2, 'rb') as wav2:
            # Extract parameters
            params1 = wav1.getparams()
            params2 = wav2.getparams()
            
            metrics["file1_channels"] = params1.nchannels
            metrics["file2_channels"] = params2.nchannels
            metrics["file1_samplerate"] = params1.framerate
            metrics["file2_samplerate"] = params2.framerate
            metrics["file1_sampwidth"] = params1.sampwidth
            metrics["file2_sampwidth"] = params2.sampwidth
            metrics["file1_frames"] = params1.nframes
            metrics["file2_frames"] = params2.nframes
            metrics["file1_duration"] = params1.nframes / params1.framerate
            metrics["file2_duration"] = params2.nframes / params2.framerate
            metrics["duration_diff"] = metrics["file2_duration"] - metrics["file1_duration"]
            
            # Read audio data
            frames1 = wav1.readframes(wav1.getnframes())
            frames2 = wav2.readframes(wav2.getnframes())
            
            audio1 = np.frombuffer(frames1, dtype=np.int16)
            audio2 = np.frombuffer(frames2, dtype=np.int16)
            
            # Compare content
            if len(audio1) == len(audio2):
                # Calculate differences
                diff = audio1.astype(np.float32) - audio2.astype(np.float32)
                metrics["mean_diff"] = float(np.mean(np.abs(diff)))
                metrics["max_diff"] = float(np.max(np.abs(diff)))
                metrics["identical"] = np.array_equal(audio1, audio2)
                
                # Calculate correlation
                if len(audio1) > 0:
                    correlation = np.corrcoef(audio1, audio2)[0, 1]
                    metrics["correlation"] = float(correlation)
            else:
                metrics["identical"] = False
                metrics["length_matches"] = False
                
    except Exception as e:
        metrics["wav_comparison_error"] = str(e)
        
    return metrics


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="VoIP metrics utilities")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two audio files")
    compare_parser.add_argument("file1", help="First audio file")
    compare_parser.add_argument("file2", help="Second audio file")
    compare_parser.add_argument("--output", help="Output file for JSON results")
    
    # Audio metrics command
    metrics_parser = subparsers.add_parser("metrics", help="Calculate audio metrics")
    metrics_parser.add_argument("original", help="Original audio file")
    metrics_parser.add_argument("received", help="Received audio file")
    metrics_parser.add_argument("--output", help="Output file for metrics report")
    metrics_parser.add_argument("--test-name", default="audio_test", 
                              help="Name for the test")
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(levelname)s - %(message)s')
    
    if args.command == "compare":
        results = compare_audio_files(args.file1, args.file2)
        
        # Print results
        print("\nAudio Comparison Results:")
        print("-" * 40)
        
        for key, value in results.items():
            print(f"{key}: {value}")
            
        # Save results if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\nResults saved to {args.output}")
            
    elif args.command == "metrics":
        # Create metrics calculator
        metrics = VoIPMetrics()
        
        # Calculate audio metrics
        results = metrics.calculate_audio_metrics(args.original, args.received)
        
        # Add to test metrics
        metrics.add_test_metrics(args.test_name, results)
        
        # Generate report
        report = metrics.generate_report(args.output)
        
        # Print report
        print(report) 