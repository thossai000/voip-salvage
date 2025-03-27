"""
Adaptive Bitrate Control

This module provides functionality for adapting codec bitrates
based on network conditions for optimal VoIP quality.
"""

import time
import logging
import threading
from typing import Dict, Any, List, Optional, Callable

from voip_benchmark.codecs.base import CodecBase

# Bitrate adjustment thresholds
DEFAULT_PACKET_LOSS_THRESHOLD = 0.05  # 5% packet loss
DEFAULT_JITTER_THRESHOLD_MS = 30.0    # 30ms jitter
DEFAULT_RTT_THRESHOLD_MS = 150.0      # 150ms RTT

# Default bitrate adjustment settings
DEFAULT_DECREASE_FACTOR = 0.8         # Decrease by 20%
DEFAULT_INCREASE_FACTOR = 1.1         # Increase by 10%
DEFAULT_MIN_BITRATE = 8000            # 8 kbps minimum
DEFAULT_MAX_BITRATE = 128000          # 128 kbps maximum
DEFAULT_ADAPTATION_INTERVAL_SEC = 1.0  # Adapt every second

# Quality presets
QUALITY_PRESETS = {
    'low': {
        'min_bitrate': 8000,    # 8 kbps
        'max_bitrate': 16000,   # 16 kbps
        'target_bitrate': 12000 # 12 kbps
    },
    'medium': {
        'min_bitrate': 16000,    # 16 kbps
        'max_bitrate': 32000,    # 32 kbps
        'target_bitrate': 24000  # 24 kbps
    },
    'high': {
        'min_bitrate': 32000,     # 32 kbps
        'max_bitrate': 64000,     # 64 kbps
        'target_bitrate': 48000   # 48 kbps
    },
    'very_high': {
        'min_bitrate': 64000,      # 64 kbps
        'max_bitrate': 128000,     # 128 kbps
        'target_bitrate': 96000    # 96 kbps
    }
}

# Adaptation strategies
class AdaptationStrategy:
    """Base class for adaptation strategies."""
    
    def __init__(self, 
                 min_bitrate: int = DEFAULT_MIN_BITRATE,
                 max_bitrate: int = DEFAULT_MAX_BITRATE):
        """Initialize the adaptation strategy.
        
        Args:
            min_bitrate: Minimum bitrate in bits per second
            max_bitrate: Maximum bitrate in bits per second
        """
        self.min_bitrate = min_bitrate
        self.max_bitrate = max_bitrate
    
    def adapt(self, 
              current_bitrate: int, 
              packet_loss: float, 
              jitter: float, 
              rtt: float) -> int:
        """Adapt the bitrate based on network conditions.
        
        Args:
            current_bitrate: Current bitrate in bits per second
            packet_loss: Packet loss rate (0.0 - 1.0)
            jitter: Jitter in milliseconds
            rtt: Round-trip time in milliseconds
            
        Returns:
            New bitrate in bits per second
        """
        raise NotImplementedError("Subclasses must implement adapt()")


class ConservativeStrategy(AdaptationStrategy):
    """Conservative adaptation strategy.
    
    This strategy decreases bitrate aggressively when network conditions
    deteriorate, and increases bitrate conservatively when conditions improve.
    """
    
    def adapt(self, 
              current_bitrate: int, 
              packet_loss: float, 
              jitter: float, 
              rtt: float) -> int:
        """Adapt the bitrate based on network conditions.
        
        Args:
            current_bitrate: Current bitrate in bits per second
            packet_loss: Packet loss rate (0.0 - 1.0)
            jitter: Jitter in milliseconds
            rtt: Round-trip time in milliseconds
            
        Returns:
            New bitrate in bits per second
        """
        # Check thresholds
        if packet_loss > DEFAULT_PACKET_LOSS_THRESHOLD:
            # Aggressive decrease on packet loss
            new_bitrate = int(current_bitrate * 0.7)
        elif jitter > DEFAULT_JITTER_THRESHOLD_MS:
            # Moderate decrease on high jitter
            new_bitrate = int(current_bitrate * 0.85)
        elif rtt > DEFAULT_RTT_THRESHOLD_MS:
            # Slight decrease on high RTT
            new_bitrate = int(current_bitrate * 0.95)
        else:
            # Slight increase on good conditions
            new_bitrate = int(current_bitrate * 1.05)
        
        # Clamp to range
        return max(self.min_bitrate, min(self.max_bitrate, new_bitrate))


class AggressiveStrategy(AdaptationStrategy):
    """Aggressive adaptation strategy.
    
    This strategy prioritizes audio quality, decreasing bitrate only
    when network conditions are very poor.
    """
    
    def adapt(self, 
              current_bitrate: int, 
              packet_loss: float, 
              jitter: float, 
              rtt: float) -> int:
        """Adapt the bitrate based on network conditions.
        
        Args:
            current_bitrate: Current bitrate in bits per second
            packet_loss: Packet loss rate (0.0 - 1.0)
            jitter: Jitter in milliseconds
            rtt: Round-trip time in milliseconds
            
        Returns:
            New bitrate in bits per second
        """
        # Check thresholds (higher thresholds than conservative)
        if packet_loss > 0.1:  # Only decrease at 10% packet loss
            # Moderate decrease on severe packet loss
            new_bitrate = int(current_bitrate * 0.8)
        elif jitter > 50:  # Only decrease at 50ms jitter
            # Slight decrease on very high jitter
            new_bitrate = int(current_bitrate * 0.9)
        elif rtt > 200:  # Only decrease at 200ms RTT
            # Minimal decrease on very high RTT
            new_bitrate = int(current_bitrate * 0.95)
        else:
            # Moderate increase on good conditions
            new_bitrate = int(current_bitrate * 1.2)
        
        # Clamp to range
        return max(self.min_bitrate, min(self.max_bitrate, new_bitrate))


class BalancedStrategy(AdaptationStrategy):
    """Balanced adaptation strategy.
    
    This strategy provides a balance between quality and stability.
    """
    
    def adapt(self, 
              current_bitrate: int, 
              packet_loss: float, 
              jitter: float, 
              rtt: float) -> int:
        """Adapt the bitrate based on network conditions.
        
        Args:
            current_bitrate: Current bitrate in bits per second
            packet_loss: Packet loss rate (0.0 - 1.0)
            jitter: Jitter in milliseconds
            rtt: Round-trip time in milliseconds
            
        Returns:
            New bitrate in bits per second
        """
        # Check thresholds (intermediate thresholds)
        if packet_loss > DEFAULT_PACKET_LOSS_THRESHOLD:
            # Standard decrease on packet loss
            new_bitrate = int(current_bitrate * DEFAULT_DECREASE_FACTOR)
        elif jitter > DEFAULT_JITTER_THRESHOLD_MS:
            # Slight decrease on high jitter
            new_bitrate = int(current_bitrate * 0.9)
        elif rtt > DEFAULT_RTT_THRESHOLD_MS:
            # Minimal decrease on high RTT
            new_bitrate = int(current_bitrate * 0.95)
        else:
            # Standard increase on good conditions
            new_bitrate = int(current_bitrate * DEFAULT_INCREASE_FACTOR)
        
        # Clamp to range
        return max(self.min_bitrate, min(self.max_bitrate, new_bitrate))


# Strategy factory
ADAPTATION_STRATEGIES = {
    'conservative': ConservativeStrategy,
    'balanced': BalancedStrategy,
    'aggressive': AggressiveStrategy
}


class AdaptiveBitrateController:
    """Controller for adaptive bitrate control.
    
    This class manages the adaptation of codec bitrate based on
    network conditions.
    """
    
    def __init__(self, 
                 codec: CodecBase,
                 strategy: str = 'balanced',
                 min_bitrate: Optional[int] = None,
                 max_bitrate: Optional[int] = None,
                 initial_bitrate: Optional[int] = None,
                 adaptation_interval: float = DEFAULT_ADAPTATION_INTERVAL_SEC):
        """Initialize the adaptive bitrate controller.
        
        Args:
            codec: The codec to control
            strategy: Adaptation strategy ('conservative', 'balanced', or 'aggressive')
            min_bitrate: Minimum bitrate in bits per second
            max_bitrate: Maximum bitrate in bits per second
            initial_bitrate: Initial bitrate in bits per second
            adaptation_interval: Interval between adaptations in seconds
        """
        self.codec = codec
        
        # Set bitrate range
        self.min_bitrate = min_bitrate if min_bitrate is not None else DEFAULT_MIN_BITRATE
        self.max_bitrate = max_bitrate if max_bitrate is not None else DEFAULT_MAX_BITRATE
        
        # Create strategy
        if strategy not in ADAPTATION_STRATEGIES:
            raise ValueError(f"Unknown strategy: {strategy}. Must be one of {list(ADAPTATION_STRATEGIES.keys())}")
        self.strategy = ADAPTATION_STRATEGIES[strategy](
            min_bitrate=self.min_bitrate,
            max_bitrate=self.max_bitrate
        )
        
        # Set initial bitrate
        self.current_bitrate = initial_bitrate if initial_bitrate is not None else codec.get_bitrate()
        self.codec.set_bitrate(self.current_bitrate)
        
        # Network condition metrics
        self.packet_loss = 0.0
        self.jitter = 0.0
        self.rtt = 0.0
        
        # Adaptation settings
        self.adaptation_interval = adaptation_interval
        self.adaptation_enabled = False
        self.adaptation_thread = None
        self.stop_event = threading.Event()
        
        # Statistics
        self.stats = {
            'adaptations': 0,
            'increases': 0,
            'decreases': 0,
            'history': []
        }
    
    def start(self) -> None:
        """Start the adaptive bitrate controller."""
        if self.adaptation_enabled:
            return
            
        self.adaptation_enabled = True
        self.stop_event.clear()
        self.adaptation_thread = threading.Thread(target=self._adaptation_loop)
        self.adaptation_thread.daemon = True
        self.adaptation_thread.start()
    
    def stop(self) -> None:
        """Stop the adaptive bitrate controller."""
        if not self.adaptation_enabled:
            return
            
        self.adaptation_enabled = False
        self.stop_event.set()
        if self.adaptation_thread:
            self.adaptation_thread.join(timeout=2.0)
            self.adaptation_thread = None
    
    def update_network_conditions(self, 
                                 packet_loss: Optional[float] = None,
                                 jitter: Optional[float] = None,
                                 rtt: Optional[float] = None) -> None:
        """Update the network condition metrics.
        
        Args:
            packet_loss: Packet loss rate (0.0 - 1.0)
            jitter: Jitter in milliseconds
            rtt: Round-trip time in milliseconds
        """
        if packet_loss is not None:
            self.packet_loss = max(0.0, min(1.0, packet_loss))
        if jitter is not None:
            self.jitter = max(0.0, jitter)
        if rtt is not None:
            self.rtt = max(0.0, rtt)
    
    def adapt_now(self) -> int:
        """Adapt the bitrate immediately.
        
        Returns:
            New bitrate in bits per second
        """
        old_bitrate = self.current_bitrate
        self.current_bitrate = self.strategy.adapt(
            self.current_bitrate,
            self.packet_loss,
            self.jitter,
            self.rtt
        )
        
        # Update codec
        self.codec.set_bitrate(self.current_bitrate)
        
        # Update stats
        self.stats['adaptations'] += 1
        if self.current_bitrate > old_bitrate:
            self.stats['increases'] += 1
        elif self.current_bitrate < old_bitrate:
            self.stats['decreases'] += 1
            
        self.stats['history'].append({
            'timestamp': time.time(),
            'old_bitrate': old_bitrate,
            'new_bitrate': self.current_bitrate,
            'packet_loss': self.packet_loss,
            'jitter': self.jitter,
            'rtt': self.rtt
        })
        
        return self.current_bitrate
    
    def _adaptation_loop(self) -> None:
        """Main adaptation loop."""
        while not self.stop_event.is_set():
            self.adapt_now()
            self.stop_event.wait(self.adaptation_interval)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the adaptation process.
        
        Returns:
            Dictionary containing adaptation statistics
        """
        return self.stats 