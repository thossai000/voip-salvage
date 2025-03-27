"""
VoIP Benchmark

This module provides the main benchmarking functionality for VoIP testing.
"""

import os
import time
import json
import wave
import threading
import tempfile
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from pathlib import Path

import numpy as np

from .codecs import get_codec_class
from .rtp.session import RTPSession
from .rtp.stream import RTPStream
from .utils.audio import read_wav_file, write_wav_file, audio_signal_statistics
from .utils.config import ConfigDict, get_default_config
from .utils.logging import BenchmarkLogger
from .utils.network import NetworkSimulator
from .utils.statistics import (
    calculate_mos, calculate_psnr, calculate_pesq, jitter_statistics,
    latency_statistics, calculate_packet_loss_burst_ratio, 
    calculate_voip_metrics, format_statistics_report
)


class VoIPBenchmark:
    """VoIP Benchmark class for testing voice quality over various network conditions."""
    
    def __init__(self, config: Optional[ConfigDict] = None):
        """Initialize the VoIP benchmark.
        
        Args:
            config: Configuration dictionary (if None, default config is used)
        """
        # Use default config if not provided
        self.config = config if config is not None else get_default_config()
        
        # Initialize logger
        log_dir = self.config['general']['log_dir']
        os.makedirs(log_dir, exist_ok=True)
        self.logger = BenchmarkLogger(log_dir, 'voip_benchmark')
        self.logger.set_configuration(self.config)
        
        # Create result directory
        self.result_dir = Path(self.config['general']['result_dir'])
        os.makedirs(self.result_dir, exist_ok=True)
        
        # Initialize stats
        self.results = []
    
    def run_benchmark(self, 
                      input_file: Union[str, Path], 
                      output_dir: Optional[Union[str, Path]] = None,
                      network_conditions: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Run the benchmark with the given input file and network conditions.
        
        Args:
            input_file: Path to input WAV file
            output_dir: Directory to store output files (if None, uses config result_dir)
            network_conditions: List of network conditions (if None, uses config)
            
        Returns:
            Dictionary with benchmark results
            
        Raises:
            FileNotFoundError: If the input file does not exist
            ValueError: If the input file is not a valid WAV file
        """
        # Validate input file
        input_path = Path(input_file)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Set output directory
        if output_dir is None:
            output_dir = self.result_dir
        else:
            output_dir = Path(output_dir)
            os.makedirs(output_dir, exist_ok=True)
        
        # Use network conditions from config if not provided
        if network_conditions is None:
            network_conditions = self.config['benchmark']['network_conditions']
        
        # Log benchmark start
        self.logger.log_event(
            'benchmark_start',
            f"Starting benchmark with input file: {input_path}",
            {'input_file': str(input_path)}
        )
        
        # Read input audio
        try:
            audio_data, audio_params = read_wav_file(str(input_path))
            
            # Log audio parameters
            self.logger.log_event(
                'audio_info',
                f"Input audio: {len(audio_data)} samples, "
                f"{audio_params['sample_rate']} Hz, "
                f"{audio_params['channels']} channels",
                audio_params
            )
            
            # Calculate audio statistics
            audio_np = np.frombuffer(audio_data, dtype=np.int16)
            audio_stats = audio_signal_statistics(audio_np)
            self.logger.log_event(
                'audio_stats',
                f"Audio statistics: RMS={audio_stats['rms']:.3f}, Peak={audio_stats['peak']:.3f}",
                audio_stats
            )
            
        except Exception as e:
            self.logger.log_error(e, {'input_file': str(input_path)})
            raise ValueError(f"Failed to read input file: {e}")
        
        # Benchmark results
        benchmark_results = {
            'input_file': str(input_path),
            'timestamp': time.time(),
            'config': self.config,
            'conditions': []
        }
        
        # Run benchmark for each network condition
        for condition in network_conditions:
            self.logger.log_event(
                'condition_start',
                f"Testing network condition: {condition['name']}",
                condition
            )
            
            # Run test with this condition
            try:
                result = self._run_condition_test(
                    condition,
                    audio_data,
                    audio_params,
                    output_dir
                )
                
                # Add to results
                benchmark_results['conditions'].append(result)
                
                # Log condition result
                self.logger.log_event(
                    'condition_result',
                    f"Network condition {condition['name']}: MOS={result['mos']:.2f}",
                    result
                )
                
            except Exception as e:
                self.logger.log_error(e, {'condition': condition})
                # Continue with next condition despite errors
        
        # Generate report
        report_path = output_dir / 'benchmark_report.json'
        with open(report_path, 'w') as f:
            json.dump(benchmark_results, f, indent=2)
        
        # Log benchmark completion
        self.logger.log_event(
            'benchmark_complete',
            f"Benchmark completed with {len(benchmark_results['conditions'])} conditions",
            {'report_path': str(report_path)}
        )
        
        # Finish logging
        self.logger.finish()
        
        return benchmark_results
    
    def _run_condition_test(self,
                           condition: Dict[str, Any],
                           audio_data: bytes,
                           audio_params: Dict[str, Any],
                           output_dir: Path) -> Dict[str, Any]:
        """Run a test with a specific network condition.
        
        Args:
            condition: Network condition parameters
            audio_data: Audio data to encode/decode
            audio_params: Audio parameters (sample_rate, channels, etc.)
            output_dir: Directory to store output files
            
        Returns:
            Dictionary with test results
        """
        # Get condition parameters
        name = condition['name']
        packet_loss = condition.get('packet_loss', 0.0)
        latency_ms = condition.get('latency', 0)
        jitter_ms = condition.get('jitter', 0)
        
        # Create temp files for encoded/decoded audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as decoded_file:
            decoded_path = decoded_file.name
        
        # Create output directory for this condition
        condition_dir = output_dir / name
        os.makedirs(condition_dir, exist_ok=True)
        
        # Path for the final decoded file
        final_decoded_path = condition_dir / 'decoded.wav'
        
        # Time execution
        start_time = time.time()
        
        try:
            # Get codec
            codec_class = get_codec_class(self.config['codec']['type'])
            codec = codec_class(self.config['codec'])
            
            # Create network simulator
            network = NetworkSimulator(
                packet_loss_rate=packet_loss,
                delay_ms=latency_ms,
                jitter_ms=jitter_ms
            )
            
            # Start network simulator
            network.start()
            
            # Prepare RTP session
            local_port = self.config['network']['port']
            remote_port = local_port + 2
            
            # Create RTP sessions (sender and receiver)
            sender_session = RTPSession(
                local_address='127.0.0.1',
                local_port=local_port,
                remote_address='127.0.0.1',
                remote_port=remote_port
            )
            
            receiver_session = RTPSession(
                local_address='127.0.0.1',
                local_port=remote_port,
                remote_address='127.0.0.1',
                remote_port=local_port
            )
            
            # Create streams
            sender_stream = RTPStream(
                session=sender_session,
                codec=codec,
                payload_type=96,  # Dynamic payload type for Opus
                frame_size=self.config['audio']['frame_size'],
                jitter_buffer_size=self.config['network']['jitter_buffer_size']
            )
            
            receiver_stream = RTPStream(
                session=receiver_session,
                codec=codec,
                payload_type=96,
                frame_size=self.config['audio']['frame_size'],
                jitter_buffer_size=self.config['network']['jitter_buffer_size']
            )
            
            # Start streams
            sender_stream.start()
            receiver_stream.start()
            
            # Split audio into frames
            frame_size = self.config['audio']['frame_size'] * audio_params['channels'] * audio_params['sample_width']
            frames = [audio_data[i:i+frame_size] for i in range(0, len(audio_data), frame_size)]
            
            # Collection for received audio
            received_audio = bytearray()
            frame_timestamps = []
            latencies = []
            jitters = []
            packet_received = []
            
            # Threading event to signal completion
            transmission_complete = threading.Event()
            
            # Callback for received frames
            def on_frame_received(frame_data, timestamp, meta):
                received_audio.extend(frame_data)
                frame_timestamps.append(timestamp)
                
                if meta and 'send_time' in meta:
                    # Calculate latency
                    latency = (time.time() - meta['send_time']) * 1000  # ms
                    latencies.append(latency)
                
                if len(frame_timestamps) >= len(frames):
                    transmission_complete.set()
            
            # Register callback
            receiver_stream.set_frame_callback(on_frame_received)
            
            # Send frames
            for i, frame in enumerate(frames):
                # Metadata with send time
                meta = {'frame_idx': i, 'send_time': time.time()}
                
                # Send through network simulator
                network.send(
                    frame,
                    lambda data: sender_stream.send_audio(data, meta)
                )
                
                # Record if packet was lost (simulated)
                packet_received.append(random.random() >= packet_loss)
                
                # Simulate frame interval timing
                time.sleep(frame_size / (audio_params['sample_rate'] * audio_params['channels'] * audio_params['sample_width']))
            
            # Wait for transmission to complete or timeout
            transmission_complete.wait(timeout=len(frames) * 0.1 + latency_ms/1000 + jitter_ms/1000 + 2.0)
            
            # Stop streams and sessions
            sender_stream.stop()
            receiver_stream.stop()
            sender_session.close()
            receiver_session.close()
            
            # Stop network simulator
            network.stop()
            
            # Get statistics
            packet_loss_rate, burst_ratio = calculate_packet_loss_burst_ratio(
                [not received for received in packet_received]
            )
            
            jitter_stats = jitter_statistics(jitters if jitters else [0])
            latency_stats = latency_statistics(latencies if latencies else [0])
            
            # Calculate average values
            actual_latency_ms = latency_stats['mean'] if latencies else latency_ms
            actual_jitter_ms = jitter_stats['mean'] if jitters else jitter_ms
            
            # Calculate MOS score
            mos = calculate_mos(
                packet_loss_rate=packet_loss_rate,
                latency_ms=actual_latency_ms,
                jitter_ms=actual_jitter_ms
            )
            
            # Write decoded audio to file
            write_wav_file(
                decoded_path,
                bytes(received_audio),
                audio_params['sample_rate'],
                audio_params['channels'],
                audio_params['sample_width']
            )
            
            # Copy to final location
            import shutil
            shutil.copy(decoded_path, final_decoded_path)
            
            # Clean up temp file
            os.unlink(decoded_path)
            
            # Calculate PSNR if there's enough received audio
            psnr = None
            if len(received_audio) >= audio_params['frame_size']:
                # Convert to numpy arrays
                original_np = np.frombuffer(audio_data[:len(received_audio)], dtype=np.int16)
                decoded_np = np.frombuffer(received_audio, dtype=np.int16)
                
                # Calculate PSNR
                psnr = calculate_psnr(original_np, decoded_np)
            
            # Try to calculate PESQ
            pesq_score = None
            try:
                # Write original to temp file for PESQ calculation
                with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as original_file:
                    original_path = original_file.name
                    write_wav_file(
                        original_path,
                        audio_data,
                        audio_params['sample_rate'],
                        audio_params['channels'],
                        audio_params['sample_width']
                    )
                
                # Calculate PESQ
                pesq_score = calculate_pesq(original_path, final_decoded_path)
                
                # Clean up temp file
                os.unlink(original_path)
            except Exception:
                # PESQ calculation is optional
                pass
            
            # Calculate comprehensive metrics
            codec_bitrate = self.config['codec']['bitrate']
            packet_size = frame_size
            packet_interval_ms = (frame_size / (audio_params['sample_rate'] * audio_params['channels'] * audio_params['sample_width'])) * 1000
            
            voip_metrics = calculate_voip_metrics(
                packet_loss_rate=packet_loss_rate,
                latency_ms=actual_latency_ms,
                jitter_ms=actual_jitter_ms,
                codec_bitrate=codec_bitrate,
                packet_size=packet_size,
                packet_interval_ms=packet_interval_ms
            )
            
            # Create complete result
            result = {
                'name': name,
                'decoded_file': str(final_decoded_path),
                'execution_time': time.time() - start_time,
                'configured': {
                    'packet_loss': packet_loss,
                    'latency_ms': latency_ms,
                    'jitter_ms': jitter_ms
                },
                'measured': {
                    'packet_loss': packet_loss_rate,
                    'latency_ms': actual_latency_ms,
                    'jitter_ms': actual_jitter_ms,
                    'burst_ratio': burst_ratio
                },
                'quality': {
                    'mos': mos,
                    'psnr': psnr,
                    'pesq': pesq_score
                },
                'statistics': {
                    'jitter': jitter_stats,
                    'latency': latency_stats
                },
                'metrics': voip_metrics
            }
            
            # Generate text report
            text_report = format_statistics_report({
                'mos': mos,
                'packet_loss_rate': packet_loss_rate,
                'latency_ms': actual_latency_ms,
                'jitter_ms': actual_jitter_ms,
                'jitter_stats': jitter_stats,
                'latency_stats': latency_stats,
                'network_bandwidth_bps': voip_metrics['network_bandwidth_bps'],
                'effective_bitrate': voip_metrics['effective_bitrate'],
                'overhead_ratio': voip_metrics['overhead_ratio'],
                'quality_rating': voip_metrics['quality_rating'],
                'latency_factor': voip_metrics['latency_factor'],
                'jitter_factor': voip_metrics['jitter_factor'],
                'packet_loss_factor': voip_metrics['packet_loss_factor'],
            }, detailed=True)
            
            # Write text report
            with open(condition_dir / 'report.txt', 'w') as f:
                f.write(text_report)
            
            return result
            
        except Exception as e:
            self.logger.log_error(e, {'condition': condition})
            
            # Return error result
            return {
                'name': name,
                'error': str(e),
                'execution_time': time.time() - start_time,
                'configured': {
                    'packet_loss': packet_loss,
                    'latency_ms': latency_ms,
                    'jitter_ms': jitter_ms
                },
                'status': 'error'
            }
    
    def compare_codecs(self,
                       input_file: Union[str, Path],
                       codecs: List[Dict[str, Any]],
                       network_condition: Optional[Dict[str, Any]] = None,
                       output_dir: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """Compare different codecs under the same network condition.
        
        Args:
            input_file: Path to input WAV file
            codecs: List of codec configurations
            network_condition: Network condition (if None, uses 'good' from config)
            output_dir: Directory to store output files (if None, uses config result_dir)
            
        Returns:
            Dictionary with comparison results
            
        Raises:
            FileNotFoundError: If the input file does not exist
            ValueError: If the input file is not a valid WAV file
        """
        # Validate input file
        input_path = Path(input_file)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Set output directory
        if output_dir is None:
            output_dir = self.result_dir / 'codec_comparison'
        else:
            output_dir = Path(output_dir)
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Use 'good' network condition if not provided
        if network_condition is None:
            network_conditions = self.config['benchmark']['network_conditions']
            for condition in network_conditions:
                if condition['name'] == 'good':
                    network_condition = condition
                    break
            
            if network_condition is None:
                # Use first condition as fallback
                network_condition = network_conditions[0]
        
        # Log comparison start
        self.logger.log_event(
            'compare_start',
            f"Comparing {len(codecs)} codecs with input file: {input_path}",
            {'input_file': str(input_path), 'codecs': codecs}
        )
        
        # Results
        comparison_results = {
            'input_file': str(input_path),
            'network_condition': network_condition,
            'timestamp': time.time(),
            'codecs': []
        }
        
        # Test each codec
        for codec_config in codecs:
            # Create temporary config with this codec
            temp_config = copy.deepcopy(self.config)
            temp_config['codec'] = codec_config
            
            # Create test instance with this config
            test = VoIPBenchmark(temp_config)
            
            # Run single test
            codec_output_dir = output_dir / codec_config['type']
            os.makedirs(codec_output_dir, exist_ok=True)
            
            # Run benchmark with single condition
            codec_result = test.run_benchmark(
                input_file=input_path,
                output_dir=codec_output_dir,
                network_conditions=[network_condition]
            )
            
            # Extract the condition result
            if codec_result.get('conditions') and len(codec_result['conditions']) > 0:
                condition_result = codec_result['conditions'][0]
                condition_result['codec'] = codec_config
                comparison_results['codecs'].append(condition_result)
            
            # Log codec result
            self.logger.log_event(
                'codec_result',
                f"Codec {codec_config['type']}: "
                f"MOS={condition_result.get('quality', {}).get('mos', 'N/A')}",
                {'codec': codec_config, 'result': condition_result}
            )
        
        # Generate report
        report_path = output_dir / 'comparison_report.json'
        with open(report_path, 'w') as f:
            json.dump(comparison_results, f, indent=2)
        
        # Log completion
        self.logger.log_event(
            'compare_complete',
            f"Codec comparison completed with {len(comparison_results['codecs'])} codecs",
            {'report_path': str(report_path)}
        )
        
        # Create summary table
        summary = self._generate_codec_comparison_summary(comparison_results)
        summary_path = output_dir / 'comparison_summary.txt'
        with open(summary_path, 'w') as f:
            f.write(summary)
        
        # Finish logging
        self.logger.finish()
        
        return comparison_results
    
    def _generate_codec_comparison_summary(self, comparison_results: Dict[str, Any]) -> str:
        """Generate a text summary of codec comparison results.
        
        Args:
            comparison_results: Codec comparison results
            
        Returns:
            Text summary
        """
        lines = []
        
        # Add header
        lines.append("Codec Comparison Summary")
        lines.append("=======================")
        lines.append("")
        
        # Add input file and network condition
        lines.append(f"Input file: {comparison_results['input_file']}")
        network = comparison_results['network_condition']
        lines.append(f"Network condition: {network['name']} "
                    f"(packet loss={network['packet_loss']*100:.1f}%, "
                    f"latency={network['latency']}ms, "
                    f"jitter={network['jitter']}ms)")
        lines.append("")
        
        # Create table header
        lines.append(f"{'Codec':<10} {'Bitrate':<10} {'MOS':<6} {'PSNR':<8} {'PESQ':<8} "
                    f"{'Quality':<10} {'Loss':<6} {'Latency':<10} {'Jitter':<8}")
        lines.append("-" * 80)
        
        # Sort codecs by MOS score
        sorted_codecs = sorted(
            comparison_results['codecs'],
            key=lambda x: x.get('quality', {}).get('mos', 0),
            reverse=True
        )
        
        # Add rows
        for codec_result in sorted_codecs:
            codec = codec_result.get('codec', {})
            quality = codec_result.get('quality', {})
            measured = codec_result.get('measured', {})
            metrics = codec_result.get('metrics', {})
            
            # Format values
            codec_name = codec.get('type', 'Unknown')
            bitrate = f"{codec.get('bitrate', 0)/1000:.1f} kbps"
            mos = f"{quality.get('mos', 'N/A'):.2f}" if quality.get('mos') is not None else 'N/A'
            psnr = f"{quality.get('psnr', 'N/A'):.1f}" if quality.get('psnr') is not None else 'N/A'
            pesq = f"{quality.get('pesq', 'N/A'):.2f}" if quality.get('pesq') is not None else 'N/A'
            quality_rating = metrics.get('quality_rating', 'Unknown')
            packet_loss = f"{measured.get('packet_loss', 0)*100:.1f}%"
            latency = f"{measured.get('latency_ms', 0):.1f} ms"
            jitter = f"{measured.get('jitter_ms', 0):.1f} ms"
            
            # Add row
            lines.append(f"{codec_name:<10} {bitrate:<10} {mos:<6} {psnr:<8} {pesq:<8} "
                        f"{quality_rating:<10} {packet_loss:<6} {latency:<10} {jitter:<8}")
        
        return "\n".join(lines)


# Missing import needed by _run_condition_test
import random


# Main entry point for CLI usage
def main():
    import argparse
    
    # Create argument parser
    parser = argparse.ArgumentParser(description="VoIP Benchmarking Tool")
    
    # Add arguments
    parser.add_argument(
        '-c', '--config',
        help="Path to configuration file",
        type=str
    )
    
    parser.add_argument(
        '-i', '--input',
        help="Path to input WAV file",
        type=str,
        required=True
    )
    
    parser.add_argument(
        '-o', '--output',
        help="Directory for output files",
        type=str
    )
    
    parser.add_argument(
        '--compare-codecs',
        help="Compare different codecs",
        action='store_true'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Load configuration
    config = None
    if args.config:
        from .utils.config import load_config_file, get_default_config, merge_configs
        try:
            file_config = load_config_file(args.config)
            config = merge_configs(get_default_config(), file_config)
        except Exception as e:
            print(f"Error loading configuration: {e}")
            return 1
    
    # Create benchmark
    benchmark = VoIPBenchmark(config)
    
    # Run benchmark or comparison
    try:
        if args.compare_codecs:
            # Define codecs to compare
            codecs = [
                {
                    'type': 'opus',
                    'bitrate': 64000,
                    'complexity': 10,
                    'adaptive_bitrate': False,
                    'fec': True,
                    'dtx': False
                },
                {
                    'type': 'opus',
                    'bitrate': 32000,
                    'complexity': 10,
                    'adaptive_bitrate': False,
                    'fec': True,
                    'dtx': False
                },
                {
                    'type': 'opus',
                    'bitrate': 16000,
                    'complexity': 10,
                    'adaptive_bitrate': False,
                    'fec': True,
                    'dtx': False
                }
            ]
            
            # Run comparison
            benchmark.compare_codecs(
                input_file=args.input,
                codecs=codecs,
                output_dir=args.output
            )
        else:
            # Run standard benchmark
            benchmark.run_benchmark(
                input_file=args.input,
                output_dir=args.output
            )
        
        print("Benchmark completed successfully.")
        return 0
        
    except Exception as e:
        print(f"Error running benchmark: {e}")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main()) 