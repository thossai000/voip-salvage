"""
Statistics Utilities

This module provides utility functions for calculating and analyzing VoIP metrics.
"""

import math
import time
import numpy as np
from typing import Dict, List, Tuple, Any, Optional, Union, Callable


def calculate_mos(
    packet_loss_rate: float,
    latency_ms: float,
    jitter_ms: float
) -> float:
    """Calculate Mean Opinion Score (MOS) based on network parameters.
    
    Implements the ITU-T E-model (G.107) for MOS estimation.
    
    Args:
        packet_loss_rate: Packet loss rate between 0.0 and 1.0
        latency_ms: One-way latency in milliseconds
        jitter_ms: Jitter in milliseconds
        
    Returns:
        Estimated MOS score between 1.0 (bad) and 5.0 (excellent)
    """
    # Convert packet loss to percentage
    packet_loss_percent = packet_loss_rate * 100.0
    
    # Factor in latency effects (Id)
    if latency_ms < 160:
        id_factor = 0
    else:
        id_factor = 0.024 * latency_ms - 3.84
        id_factor = max(0, min(id_factor, 14))  # Cap at 14
    
    # Factor in packet loss effects (Ie-eff)
    ie_eff = 30 * math.log(1 + 15 * packet_loss_percent) / math.log(16)
    
    # Factor in jitter (simplified approximation)
    jitter_factor = 0
    if jitter_ms > 40:
        jitter_factor = (jitter_ms - 40) * 0.05
        jitter_factor = min(jitter_factor, 10)
    
    # Calculate R-value (ITU-T G.107)
    r_value = 93.2 - id_factor - ie_eff - jitter_factor
    
    # Convert R-value to MOS (ITU-T P.800)
    if r_value < 0:
        mos = 1.0
    elif r_value > 100:
        mos = 4.5
    else:
        mos = 1 + 0.035 * r_value + r_value * (r_value - 60) * (100 - r_value) * 7e-6
    
    # Ensure MOS is within valid range
    return max(1.0, min(5.0, mos))


def calculate_psnr(
    original: np.ndarray,
    processed: np.ndarray,
    max_value: float = 32767.0
) -> float:
    """Calculate Peak Signal-to-Noise Ratio (PSNR) between original and processed audio.
    
    Args:
        original: Original audio as numpy array
        processed: Processed audio as numpy array
        max_value: Maximum value of the signal (default is for 16-bit audio)
        
    Returns:
        PSNR in dB
    """
    # Make sure arrays are the same length
    min_len = min(len(original), len(processed))
    original = original[:min_len]
    processed = processed[:min_len]
    
    # Calculate MSE
    mse = np.mean((original - processed) ** 2)
    if mse == 0:
        return float('inf')
    
    # Calculate PSNR
    return 20 * math.log10(max_value) - 10 * math.log10(mse)


def calculate_pesq(original_path: str, processed_path: str) -> Optional[float]:
    """Calculate Perceptual Evaluation of Speech Quality (PESQ).
    
    This is a wrapper for the PESQ algorithm, which requires external libraries.
    
    Args:
        original_path: Path to original audio file (wav)
        processed_path: Path to processed audio file (wav)
        
    Returns:
        PESQ score or None if calculation fails
    """
    try:
        import pesq
        import soundfile as sf
        
        # Read audio files
        orig_audio, orig_rate = sf.read(original_path)
        proc_audio, proc_rate = sf.read(processed_path)
        
        # PESQ requires sampling rate to be either 8000 or 16000 Hz
        if orig_rate not in [8000, 16000] or proc_rate not in [8000, 16000]:
            return None
        
        # Make sure arrays are the same length
        min_len = min(len(orig_audio), len(proc_audio))
        orig_audio = orig_audio[:min_len]
        proc_audio = proc_audio[:min_len]
        
        # Calculate PESQ
        return pesq.pesq(orig_rate, orig_audio, proc_audio, 'wb')
    except (ImportError, Exception):
        return None


def jitter_statistics(jitter_values: List[float]) -> Dict[str, float]:
    """Calculate statistics for jitter values.
    
    Args:
        jitter_values: List of jitter measurements in milliseconds
        
    Returns:
        Dictionary with statistics (mean, median, stddev, min, max, percentiles)
    """
    if not jitter_values:
        return {
            'mean': 0.0,
            'median': 0.0,
            'stddev': 0.0,
            'min': 0.0,
            'max': 0.0,
            'p95': 0.0,
            'p99': 0.0
        }
    
    jitter_array = np.array(jitter_values)
    
    return {
        'mean': float(np.mean(jitter_array)),
        'median': float(np.median(jitter_array)),
        'stddev': float(np.std(jitter_array)),
        'min': float(np.min(jitter_array)),
        'max': float(np.max(jitter_array)),
        'p95': float(np.percentile(jitter_array, 95)),
        'p99': float(np.percentile(jitter_array, 99))
    }


def latency_statistics(latency_values: List[float]) -> Dict[str, float]:
    """Calculate statistics for latency values.
    
    Args:
        latency_values: List of latency measurements in milliseconds
        
    Returns:
        Dictionary with statistics (mean, median, stddev, min, max, percentiles)
    """
    return jitter_statistics(latency_values)  # Same calculation method


def calculate_packet_loss_burst_ratio(
    packet_loss_events: List[bool]
) -> Tuple[float, float]:
    """Calculate packet loss and burst ratio.
    
    Args:
        packet_loss_events: List of boolean values (True if packet lost, False if received)
        
    Returns:
        Tuple of (packet_loss_rate, burst_ratio)
    """
    if not packet_loss_events:
        return 0.0, 0.0
    
    # Calculate packet loss rate
    loss_count = sum(1 for event in packet_loss_events if event)
    total_count = len(packet_loss_events)
    loss_rate = loss_count / total_count if total_count > 0 else 0.0
    
    # Calculate burst ratio (consecutive losses)
    burst_count = 0
    i = 0
    while i < total_count:
        if packet_loss_events[i]:
            burst_start = i
            while i < total_count and packet_loss_events[i]:
                i += 1
            burst_length = i - burst_start
            if burst_length > 1:
                burst_count += burst_length
        else:
            i += 1
    
    # Calculate burst ratio
    expected_burst = loss_rate * total_count
    burst_ratio = burst_count / expected_burst if expected_burst > 0 else 0.0
    
    return loss_rate, burst_ratio


class RollingStatistics:
    """Calculate statistics over a rolling window of values."""
    
    def __init__(self, window_size: int = 100):
        """Initialize the rolling statistics calculator.
        
        Args:
            window_size: Number of samples to keep in the window
        """
        self.window_size = max(2, window_size)
        self.values = []
        self.sum = 0.0
        self.sum_squared = 0.0
        self.last_update_time = time.time()
    
    def add(self, value: float) -> None:
        """Add a value to the rolling window.
        
        Args:
            value: Value to add
        """
        self.values.append(value)
        self.sum += value
        self.sum_squared += value * value
        
        # Remove oldest value if window is full
        if len(self.values) > self.window_size:
            oldest = self.values.pop(0)
            self.sum -= oldest
            self.sum_squared -= oldest * oldest
        
        self.last_update_time = time.time()
    
    def get_statistics(self) -> Dict[str, float]:
        """Get statistics for the current window.
        
        Returns:
            Dictionary with statistics (count, mean, variance, stddev, min, max)
        """
        count = len(self.values)
        
        if count == 0:
            return {
                'count': 0,
                'mean': 0.0,
                'variance': 0.0,
                'stddev': 0.0,
                'min': 0.0,
                'max': 0.0,
                'age': 0.0
            }
        
        mean = self.sum / count
        
        # Calculate variance
        if count > 1:
            variance = (self.sum_squared - (self.sum * self.sum) / count) / (count - 1)
            variance = max(0.0, variance)  # Ensure non-negative due to floating point errors
        else:
            variance = 0.0
        
        return {
            'count': count,
            'mean': mean,
            'variance': variance,
            'stddev': math.sqrt(variance),
            'min': min(self.values),
            'max': max(self.values),
            'age': time.time() - self.last_update_time
        }


def calculate_voip_metrics(
    packet_loss_rate: float,
    latency_ms: float,
    jitter_ms: float,
    codec_bitrate: int,
    packet_size: int,
    packet_interval_ms: int
) -> Dict[str, Any]:
    """Calculate comprehensive VoIP quality metrics.
    
    Args:
        packet_loss_rate: Packet loss rate between 0.0 and 1.0
        latency_ms: One-way latency in milliseconds
        jitter_ms: Jitter in milliseconds
        codec_bitrate: Codec bitrate in bits per second
        packet_size: RTP packet size in bytes
        packet_interval_ms: Packet interval in milliseconds
        
    Returns:
        Dictionary with VoIP quality metrics
    """
    # Calculate MOS
    mos = calculate_mos(packet_loss_rate, latency_ms, jitter_ms)
    
    # Calculate effective bitrate considering packet loss
    effective_bitrate = codec_bitrate * (1.0 - packet_loss_rate)
    
    # Packet rate
    packet_rate = 1000.0 / packet_interval_ms
    
    # Overhead calculation (assuming IPv4 + UDP + RTP = 40 bytes)
    header_size = 40  # bytes
    total_packet_size = packet_size + header_size
    overhead_ratio = header_size / total_packet_size
    
    # Network bandwidth required
    network_bandwidth_bps = total_packet_size * 8 * packet_rate
    
    # Quality assessment
    quality_rating = "Unknown"
    if mos >= 4.3:
        quality_rating = "Excellent"
    elif mos >= 4.0:
        quality_rating = "Good"
    elif mos >= 3.6:
        quality_rating = "Fair"
    elif mos >= 3.1:
        quality_rating = "Poor"
    else:
        quality_rating = "Bad"
    
    # Call quality factors
    latency_factor = "Good" if latency_ms < 150 else ("Fair" if latency_ms < 300 else "Poor")
    jitter_factor = "Good" if jitter_ms < 20 else ("Fair" if jitter_ms < 50 else "Poor")
    packet_loss_factor = "Good" if packet_loss_rate < 0.01 else ("Fair" if packet_loss_rate < 0.03 else "Poor")
    
    return {
        'mos': mos,
        'quality_rating': quality_rating,
        'effective_bitrate': effective_bitrate,
        'network_bandwidth_bps': network_bandwidth_bps,
        'overhead_ratio': overhead_ratio,
        'packet_rate': packet_rate,
        'latency_factor': latency_factor,
        'jitter_factor': jitter_factor,
        'packet_loss_factor': packet_loss_factor
    }


def audio_signal_statistics(audio_data: np.ndarray) -> Dict[str, float]:
    """Calculate statistics for audio signal.
    
    Args:
        audio_data: Audio data as numpy array
        
    Returns:
        Dictionary with statistics (rms, peak, dynamic_range, zero_crossings)
    """
    if len(audio_data) == 0:
        return {
            'rms': 0.0,
            'peak': 0.0,
            'dynamic_range': 0.0,
            'zero_crossings': 0.0,
            'silence_percentage': 100.0
        }
    
    # RMS level
    rms = np.sqrt(np.mean(np.square(audio_data)))
    
    # Peak level
    peak = np.max(np.abs(audio_data))
    
    # Dynamic range (crest factor)
    dynamic_range = 20 * np.log10(peak / rms) if rms > 0 else 0.0
    
    # Zero crossing rate
    zero_crossings = np.sum(np.abs(np.diff(np.signbit(audio_data)))) / len(audio_data)
    
    # Silence detection (simplified)
    silence_threshold = 0.01  # -40 dB
    silence_samples = np.sum(np.abs(audio_data) < silence_threshold)
    silence_percentage = 100.0 * silence_samples / len(audio_data)
    
    return {
        'rms': float(rms),
        'peak': float(peak),
        'dynamic_range': float(dynamic_range),
        'zero_crossings': float(zero_crossings),
        'silence_percentage': float(silence_percentage)
    }


def format_statistics_report(stats: Dict[str, Any], detailed: bool = False) -> str:
    """Format statistics into a readable report.
    
    Args:
        stats: Dictionary of statistics
        detailed: Whether to include detailed statistics
        
    Returns:
        Formatted report as string
    """
    report = []
    
    # Add header
    report.append("VoIP Quality Report")
    report.append("=================")
    report.append("")
    
    # Add quality metrics
    if 'mos' in stats:
        report.append(f"MOS Score: {stats['mos']:.2f} ({stats.get('quality_rating', 'Unknown')})")
    
    if 'packet_loss_rate' in stats:
        report.append(f"Packet Loss: {stats['packet_loss_rate'] * 100:.2f}% ({stats.get('packet_loss_factor', 'Unknown')})")
    
    if 'latency_ms' in stats:
        report.append(f"Latency: {stats['latency_ms']:.1f} ms ({stats.get('latency_factor', 'Unknown')})")
    
    if 'jitter_ms' in stats:
        report.append(f"Jitter: {stats['jitter_ms']:.1f} ms ({stats.get('jitter_factor', 'Unknown')})")
    
    # Network metrics
    report.append("")
    report.append("Network Metrics")
    report.append("--------------")
    
    if 'network_bandwidth_bps' in stats:
        report.append(f"Network Bandwidth: {stats['network_bandwidth_bps']/1000:.1f} kbps")
    
    if 'effective_bitrate' in stats:
        report.append(f"Effective Bitrate: {stats['effective_bitrate']/1000:.1f} kbps")
    
    if 'overhead_ratio' in stats:
        report.append(f"Protocol Overhead: {stats['overhead_ratio']*100:.1f}%")
    
    # Include additional detailed stats if requested
    if detailed:
        report.append("")
        report.append("Detailed Statistics")
        report.append("------------------")
        
        # Include jitter statistics
        if 'jitter_stats' in stats:
            js = stats['jitter_stats']
            report.append(f"Jitter (ms): min={js['min']:.1f}, avg={js['mean']:.1f}, max={js['max']:.1f}, p95={js['p95']:.1f}")
        
        # Include latency statistics
        if 'latency_stats' in stats:
            ls = stats['latency_stats']
            report.append(f"Latency (ms): min={ls['min']:.1f}, avg={ls['mean']:.1f}, max={ls['max']:.1f}, p95={ls['p95']:.1f}")
        
        # Include audio statistics
        if 'audio_stats' in stats:
            aus = stats['audio_stats']
            report.append(f"Audio: RMS={aus['rms']:.3f}, Peak={aus['peak']:.3f}, Dynamics={aus['dynamic_range']:.1f} dB")
            report.append(f"Silence: {aus['silence_percentage']:.1f}% of samples")
    
    return "\n".join(report) 