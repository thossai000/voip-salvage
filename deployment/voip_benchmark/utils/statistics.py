"""
Statistics Utilities

This module provides utility functions for calculating VoIP quality
metrics and statistics.
"""

import math
import numpy as np
from typing import Dict, Any, List, Tuple, Optional, Union


def calculate_packet_loss_ratio(packets_sent: int, packets_received: int) -> float:
    """Calculate packet loss ratio.
    
    Args:
        packets_sent: Number of packets sent
        packets_received: Number of packets received
        
    Returns:
        Packet loss ratio (0.0 to 1.0)
    """
    if packets_sent == 0:
        return 0.0
    
    return max(0.0, min(1.0, (packets_sent - packets_received) / packets_sent))


def calculate_packet_loss_burst_ratio(loss_pattern: List[bool]) -> float:
    """Calculate packet loss burst ratio.
    
    The burst ratio indicates how packet loss is distributed:
    - Value < 1.0: Random/distributed losses
    - Value = 1.0: No correlation between losses
    - Value > 1.0: Bursty loss pattern
    
    Args:
        loss_pattern: List of booleans indicating packet loss (True = lost)
        
    Returns:
        Packet loss burst ratio
    """
    if not loss_pattern or all(not lost for lost in loss_pattern):
        return 1.0
    
    # Count losses
    num_losses = sum(loss_pattern)
    
    # Count loss bursts (sequences of consecutive lost packets)
    bursts = 0
    in_burst = False
    for lost in loss_pattern:
        if lost and not in_burst:
            bursts += 1
            in_burst = True
        elif not lost:
            in_burst = False
    
    # Calculate expected bursts if losses were random
    loss_probability = num_losses / len(loss_pattern)
    expected_bursts = num_losses * (1 - loss_probability)
    
    # Handle edge case where all packets are lost
    if expected_bursts == 0:
        return 1.0
    
    # Calculate burst ratio
    return bursts / expected_bursts


def calculate_jitter_statistics(jitter_values: List[float]) -> Dict[str, float]:
    """Calculate statistics for jitter values.
    
    Args:
        jitter_values: List of jitter measurements in milliseconds
        
    Returns:
        Dictionary with jitter statistics
    """
    if not jitter_values:
        return {
            'mean': 0.0,
            'median': 0.0,
            'min': 0.0,
            'max': 0.0,
            'p95': 0.0,
            'p99': 0.0,
            'std_dev': 0.0
        }
    
    # Convert to numpy array for efficient calculations
    jitter_array = np.array(jitter_values)
    
    # Calculate statistics
    stats = {
        'mean': float(np.mean(jitter_array)),
        'median': float(np.median(jitter_array)),
        'min': float(np.min(jitter_array)),
        'max': float(np.max(jitter_array)),
        'p95': float(np.percentile(jitter_array, 95)),
        'p99': float(np.percentile(jitter_array, 99)),
        'std_dev': float(np.std(jitter_array))
    }
    
    return stats


def calculate_mos(
    packet_loss_ratio: float,
    latency: float = 0.0,
    jitter: float = 0.0,
    codec: str = 'opus'
) -> float:
    """Calculate Mean Opinion Score (MOS) for VoIP quality.
    
    MOS is a measure of perceived audio quality:
    - 5: Excellent
    - 4: Good
    - 3: Fair
    - 2: Poor
    - 1: Bad
    
    Args:
        packet_loss_ratio: Packet loss ratio (0.0 to 1.0)
        latency: One-way latency in milliseconds
        jitter: Jitter in milliseconds
        codec: Codec name ('opus', 'g711', etc.)
        
    Returns:
        Estimated MOS (1.0 to 5.0)
    """
    # Convert percentage to ratio if needed
    if packet_loss_ratio > 1.0:
        packet_loss_ratio = packet_loss_ratio / 100.0
    
    # Base R-factor parameters based on codec
    if codec.lower() == 'opus':
        # Opus has excellent quality and resilience
        r0 = 93.5
        # Opus handles packet loss better than other codecs
        ie = 11  # Lower value means better resilience
        bpl = 20  # Higher value means better handling of burst losses
    elif codec.lower() in ['g711', 'pcmu', 'pcma']:
        # G.711 (PCM μ-law or A-law)
        r0 = 93.2
        ie = 33
        bpl = 10
    elif codec.lower() in ['g722']:
        # G.722
        r0 = 93.0
        ie = 23
        bpl = 15
    elif codec.lower() in ['g729']:
        # G.729
        r0 = 92.0
        ie = 35
        bpl = 10
    else:
        # Default/generic codec
        r0 = 90.0
        ie = 30
        bpl = 10
    
    # Calculate R-factor components
    
    # Id: Delay impairment
    # - Up to 160ms is generally acceptable
    # - Beyond 160ms, quality decreases
    # - 400ms or more is very poor
    if latency < 160:
        id_delay = 0
    else:
        id_delay = 0.024 * latency + 0.11 * (latency - 120) * int(latency - 120 > 0)
    
    # Ie_eff: Effective equipment impairment, including packet loss effects
    # Higher packet loss = higher impairment
    # The formula accounts for burst packet loss being more detrimental than random loss
    ie_eff = ie + (95 - ie) * (packet_loss_ratio / (packet_loss_ratio + bpl))
    
    # Add jitter penalty (simplified model)
    jitter_penalty = min(10, jitter * 0.5)  # 2ms jitter = 1 point penalty, capped at 10
    
    # Calculate R-factor (0-100 scale)
    r_factor = r0 - id_delay - ie_eff - jitter_penalty
    
    # Convert R-factor to MOS (1-5 scale)
    if r_factor < 0:
        mos = 1.0
    elif r_factor > 100:
        mos = 5.0
    else:
        # Standard ITU-T G.107 conversion formula
        mos = 1 + 0.035 * r_factor + r_factor * (r_factor - 60) * (100 - r_factor) * 7e-6
    
    # Ensure MOS is within valid range
    return max(1.0, min(5.0, mos))


def calculate_psnr(original: np.ndarray, processed: np.ndarray) -> float:
    """Calculate Peak Signal-to-Noise Ratio (PSNR) between original and processed audio.
    
    Higher PSNR values indicate better quality.
    
    Args:
        original: Original audio samples as numpy array
        processed: Processed audio samples as numpy array
        
    Returns:
        PSNR value in dB
    """
    # Make sure arrays are the same length for comparison
    min_length = min(len(original), len(processed))
    original = original[:min_length]
    processed = processed[:min_length]
    
    # Calculate MSE (Mean Squared Error)
    mse = np.mean((original - processed) ** 2)
    
    # Avoid division by zero
    if mse == 0:
        return 100.0  # Perfect match
    
    # Calculate PSNR
    # For 16-bit audio, max value is 32767
    max_value = np.max(np.abs(original))
    psnr = 20 * math.log10(max_value / math.sqrt(mse))
    
    return psnr


def calculate_compression_ratio(original_size: int, compressed_size: int) -> float:
    """Calculate compression ratio.
    
    Args:
        original_size: Size of original data in bytes
        compressed_size: Size of compressed data in bytes
        
    Returns:
        Compression ratio (compressed_size / original_size)
    """
    if original_size == 0:
        return 0.0
    
    return compressed_size / original_size


def calculate_audio_level(samples: np.ndarray) -> Dict[str, float]:
    """Calculate audio level statistics.
    
    Args:
        samples: Audio samples as numpy array
        
    Returns:
        Dictionary with audio level statistics
    """
    if len(samples) == 0:
        return {
            'rms': 0.0,
            'peak': 0.0,
            'crest_factor': 0.0
        }
    
    # Calculate RMS level
    rms = np.sqrt(np.mean(samples.astype(np.float64) ** 2))
    
    # Calculate peak level
    peak = np.max(np.abs(samples))
    
    # Calculate crest factor (peak/rms ratio)
    crest_factor = peak / rms if rms > 0 else 0.0
    
    return {
        'rms': float(rms),
        'peak': float(peak),
        'crest_factor': float(crest_factor)
    }


def generate_voip_report(
    call_duration: float,
    packet_stats: Dict[str, int],
    audio_stats: Dict[str, Any],
    network_stats: Optional[Dict[str, Any]] = None,
    codec_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Generate a comprehensive VoIP quality report.
    
    Args:
        call_duration: Call duration in seconds
        packet_stats: Packet statistics (sent, received, lost, etc.)
        audio_stats: Audio statistics
        network_stats: Network statistics (optional)
        codec_info: Codec information (optional)
        
    Returns:
        Dictionary with VoIP quality report
    """
    report = {
        'call_duration': call_duration,
        'packet_stats': {
            'sent': packet_stats.get('sent', 0),
            'received': packet_stats.get('received', 0),
            'lost': packet_stats.get('sent', 0) - packet_stats.get('received', 0),
            'out_of_order': packet_stats.get('out_of_order', 0),
            'duplicates': packet_stats.get('duplicates', 0),
        },
    }
    
    # Calculate packet loss ratio
    packets_sent = packet_stats.get('sent', 0)
    packets_received = packet_stats.get('received', 0)
    packet_loss_ratio = calculate_packet_loss_ratio(packets_sent, packets_received)
    report['packet_stats']['loss_ratio'] = packet_loss_ratio
    
    # Add audio stats
    if audio_stats:
        report['audio_stats'] = audio_stats
    
    # Add network stats
    if network_stats:
        report['network_stats'] = network_stats
        
        # Calculate MOS if we have the necessary data
        if 'latency' in network_stats and 'jitter' in network_stats:
            codec_name = codec_info.get('name', 'opus') if codec_info else 'opus'
            mos = calculate_mos(
                packet_loss_ratio,
                network_stats.get('latency', 0.0),
                network_stats.get('jitter', 0.0),
                codec_name
            )
            report['quality_metrics'] = {'mos': mos}
    
    # Add codec info
    if codec_info:
        report['codec_info'] = codec_info
        
        # Calculate compression ratio if we have the necessary data
        if 'original_size' in audio_stats and 'encoded_size' in audio_stats:
            compression_ratio = calculate_compression_ratio(
                audio_stats['original_size'],
                audio_stats['encoded_size']
            )
            report['compression'] = {
                'ratio': compression_ratio,
                'saving_percent': (1 - compression_ratio) * 100
            }
    
    return report 