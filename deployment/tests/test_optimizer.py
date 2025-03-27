"""
Test suite for adaptive bitrate optimization.

This module contains tests for the adaptive bitrate optimization
functionality, which adjusts codec parameters based on network conditions.
"""

import pytest
import time
import numpy as np
from typing import Dict, List, Tuple

from voip_benchmark.codecs.opus import OpusCodec
from voip_benchmark.codecs.adaptive_bitrate import (
    AdaptiveBitrateController,
    NetworkStats,
    BALANCED_STRATEGY,
    QUALITY_STRATEGY,
    AGGRESSIVE_STRATEGY,
)


def test_network_stats_calculation():
    """Test the calculation of network statistics."""
    # Create empty network stats
    stats = NetworkStats()
    
    # Add data points
    for _ in range(10):
        stats.add_packet(100, 0, False)  # 100 bytes, no loss, in order
    
    assert stats.packets_received == 10
    assert stats.packet_loss_rate == 0.0
    assert stats.average_packet_size == 100
    assert stats.out_of_order_rate == 0.0
    
    # Add some packet loss and out-of-order packets
    for _ in range(5):
        stats.add_packet(100, 0, False)  # Normal packet
    stats.add_packet_loss()
    stats.add_packet_loss()
    stats.add_packet(100, 0, True)  # Out of order
    
    # Total: 16 received, 2 lost, 1 out of order
    assert stats.packets_received == 16
    assert stats.packets_lost == 2
    assert stats.packets_out_of_order == 1
    assert stats.packet_loss_rate == 2 / 18  # 2 lost out of 18 total
    assert abs(stats.out_of_order_rate - 1/16) < 0.001  # 1 out of order out of 16 received
    
    # Test reset
    stats.reset()
    assert stats.packets_received == 0
    assert stats.packets_lost == 0
    assert stats.packets_out_of_order == 0
    assert stats.packet_loss_rate == 0.0
    assert stats.out_of_order_rate == 0.0


def test_adaptive_bitrate_controller_initialization():
    """Test the initialization of the adaptive bitrate controller."""
    # Create codec
    codec = OpusCodec()
    
    # Initialize controller with default settings
    controller = AdaptiveBitrateController(codec)
    assert controller.codec == codec
    assert controller.min_bitrate == 8000
    assert controller.max_bitrate == 128000
    assert controller.adjustment_interval == 1.0
    assert controller.strategy == BALANCED_STRATEGY
    
    # Initialize with custom settings
    controller = AdaptiveBitrateController(
        codec,
        min_bitrate=16000,
        max_bitrate=64000,
        adjustment_interval=2.0,
        strategy=QUALITY_STRATEGY
    )
    assert controller.min_bitrate == 16000
    assert controller.max_bitrate == 64000
    assert controller.adjustment_interval == 2.0
    assert controller.strategy == QUALITY_STRATEGY


def test_adaptive_bitrate_balanced_strategy():
    """Test the balanced strategy for adaptive bitrate control."""
    # Create codec
    codec = OpusCodec(bitrate=32000)
    
    # Initialize controller with balanced strategy
    controller = AdaptiveBitrateController(
        codec,
        min_bitrate=8000,
        max_bitrate=128000,
        strategy=BALANCED_STRATEGY
    )
    
    # Reset stats
    controller.network_stats.reset()
    
    # Test with good network conditions
    for _ in range(100):
        controller.network_stats.add_packet(100, 0, False)
    
    # Update bitrate (should increase slightly)
    previous_bitrate = codec.bitrate
    controller.update_bitrate()
    assert codec.bitrate > previous_bitrate
    assert codec.bitrate <= controller.max_bitrate
    
    # Test with moderate packet loss
    controller.network_stats.reset()
    for _ in range(90):
        controller.network_stats.add_packet(100, 0, False)
    for _ in range(10):
        controller.network_stats.add_packet_loss()
    
    # Update bitrate (should decrease)
    previous_bitrate = codec.bitrate
    controller.update_bitrate()
    assert codec.bitrate < previous_bitrate
    assert codec.bitrate >= controller.min_bitrate


def test_adaptive_bitrate_quality_strategy():
    """Test the quality strategy for adaptive bitrate control."""
    # Create codec
    codec = OpusCodec(bitrate=32000)
    
    # Initialize controller with quality strategy
    controller = AdaptiveBitrateController(
        codec,
        min_bitrate=8000,
        max_bitrate=128000,
        strategy=QUALITY_STRATEGY
    )
    
    # Reset stats
    controller.network_stats.reset()
    
    # Test with good network conditions
    for _ in range(100):
        controller.network_stats.add_packet(100, 0, False)
    
    # Update bitrate (should increase more than with balanced strategy)
    previous_bitrate = codec.bitrate
    controller.update_bitrate()
    assert codec.bitrate > previous_bitrate
    assert codec.bitrate <= controller.max_bitrate
    
    # Save the new bitrate to compare with balanced strategy
    quality_bitrate = codec.bitrate
    
    # Create a new controller with balanced strategy for comparison
    codec.set_bitrate(32000)  # Reset bitrate
    balanced_controller = AdaptiveBitrateController(
        codec,
        min_bitrate=8000,
        max_bitrate=128000,
        strategy=BALANCED_STRATEGY
    )
    
    # Use the same network conditions
    for _ in range(100):
        balanced_controller.network_stats.add_packet(100, 0, False)
    
    # Update bitrate
    balanced_controller.update_bitrate()
    balanced_bitrate = codec.bitrate
    
    # Quality strategy should be more aggressive in increasing bitrate
    assert quality_bitrate >= balanced_bitrate


def test_adaptive_bitrate_aggressive_strategy():
    """Test the aggressive strategy for adaptive bitrate control."""
    # Create codec
    codec = OpusCodec(bitrate=32000)
    
    # Initialize controller with aggressive strategy
    controller = AdaptiveBitrateController(
        codec,
        min_bitrate=8000,
        max_bitrate=128000,
        strategy=AGGRESSIVE_STRATEGY
    )
    
    # Reset stats
    controller.network_stats.reset()
    
    # Test with moderate packet loss
    for _ in range(90):
        controller.network_stats.add_packet(100, 0, False)
    for _ in range(10):
        controller.network_stats.add_packet_loss()
    
    # Update bitrate (should decrease more than with balanced strategy)
    previous_bitrate = codec.bitrate
    controller.update_bitrate()
    assert codec.bitrate < previous_bitrate
    assert codec.bitrate >= controller.min_bitrate
    
    # Save the new bitrate to compare with balanced strategy
    aggressive_bitrate = codec.bitrate
    
    # Create a new controller with balanced strategy for comparison
    codec.set_bitrate(32000)  # Reset bitrate
    balanced_controller = AdaptiveBitrateController(
        codec,
        min_bitrate=8000,
        max_bitrate=128000,
        strategy=BALANCED_STRATEGY
    )
    
    # Use the same network conditions
    for _ in range(90):
        balanced_controller.network_stats.add_packet(100, 0, False)
    for _ in range(10):
        balanced_controller.network_stats.add_packet_loss()
    
    # Update bitrate
    balanced_controller.update_bitrate()
    balanced_bitrate = codec.bitrate
    
    # Aggressive strategy should be more aggressive in decreasing bitrate
    assert aggressive_bitrate <= balanced_bitrate 