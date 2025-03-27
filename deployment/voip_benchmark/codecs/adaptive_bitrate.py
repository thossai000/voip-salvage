"""
Adaptive Bitrate Control for VoIP Codecs

This module provides adaptive bitrate control functionality for VoIP codecs,
allowing dynamic adjustment of codec bitrate based on network conditions.
"""

import time
import threading
import logging
from enum import Enum
from typing import Dict, Any, Optional, Callable, List, Tuple

# Default values
DEFAULT_MIN_BITRATE = 8000    # 8 kbps
DEFAULT_MAX_BITRATE = 128000  # 128 kbps
DEFAULT_START_BITRATE = 24000 # 24 kbps
DEFAULT_STEP_SIZE = 4000      # 4 kbps
DEFAULT_CONGESTION_THRESHOLD = 0.05  # 5% packet loss
DEFAULT_STABILITY_PERIOD = 5.0  # 5 seconds


class AdaptiveBitrateStrategy(Enum):
    """Adaptive bitrate control strategies."""
    
    QUALITY = 'quality'       # Prefers quality, reduces bitrate only when necessary
    BALANCED = 'balanced'     # Balanced approach between quality and stability
    AGGRESSIVE = 'aggressive' # Aggressively reduces bitrate to minimize issues


class AdaptiveBitrateController:
    """Controller for adaptive bitrate in VoIP codecs.
    
    This class monitors network conditions and adjusts codec bitrate
    accordingly to optimize voice quality while maintaining stability.
    """
    
    def __init__(self, 
                 min_bitrate: int = DEFAULT_MIN_BITRATE,
                 max_bitrate: int = DEFAULT_MAX_BITRATE,
                 start_bitrate: int = DEFAULT_START_BITRATE,
                 step_size: int = DEFAULT_STEP_SIZE,
                 congestion_threshold: float = DEFAULT_CONGESTION_THRESHOLD,
                 stability_period: float = DEFAULT_STABILITY_PERIOD,
                 strategy: AdaptiveBitrateStrategy = AdaptiveBitrateStrategy.BALANCED):
        """Initialize the adaptive bitrate controller.
        
        Args:
            min_bitrate: Minimum bitrate in bits per second
            max_bitrate: Maximum bitrate in bits per second
            start_bitrate: Starting bitrate in bits per second
            step_size: Step size for bitrate adjustments in bits per second
            congestion_threshold: Packet loss threshold to trigger bitrate reduction
            stability_period: Minimum time between bitrate adjustments in seconds
            strategy: Adaptive bitrate control strategy
        """
        # Bitrate parameters
        self.min_bitrate = min_bitrate
        self.max_bitrate = max_bitrate
        self.step_size = step_size
        self.current_bitrate = min(max(start_bitrate, min_bitrate), max_bitrate)
        
        # Network condition parameters
        self.congestion_threshold = congestion_threshold
        self.stability_period = stability_period
        self.strategy = strategy
        
        # State
        self.last_adjustment_time = 0
        self.packet_loss_history: List[float] = []
        self.jitter_history: List[float] = []
        self.rtt_history: List[float] = []
        self.bitrate_history: List[Tuple[float, int]] = []  # (timestamp, bitrate)
        
        # Stats
        self.stats = {
            'adjustments_up': 0,
            'adjustments_down': 0,
            'congestion_events': 0,
            'stability_events': 0
        }
        
        # Callback for bitrate changes
        self.bitrate_change_callback: Optional[Callable[[int], None]] = None
        
        # Initial record
        self._record_bitrate()
    
    def set_bitrate_change_callback(self, callback: Callable[[int], None]) -> None:
        """Set a callback for bitrate changes.
        
        Args:
            callback: Function to call when bitrate changes.
                     Takes the new bitrate as an argument.
        """
        self.bitrate_change_callback = callback
    
    def update_network_stats(self, 
                            packet_loss: float, 
                            jitter: Optional[float] = None,
                            rtt: Optional[float] = None) -> None:
        """Update network statistics and adjust bitrate if needed.
        
        Args:
            packet_loss: Current packet loss ratio (0.0 to 1.0)
            jitter: Network jitter in milliseconds (optional)
            rtt: Round-trip time in milliseconds (optional)
        """
        # Record network stats
        self.packet_loss_history.append(packet_loss)
        if jitter is not None:
            self.jitter_history.append(jitter)
        if rtt is not None:
            self.rtt_history.append(rtt)
        
        # Keep history at a reasonable size
        max_history = 100
        if len(self.packet_loss_history) > max_history:
            self.packet_loss_history = self.packet_loss_history[-max_history:]
        if len(self.jitter_history) > max_history:
            self.jitter_history = self.jitter_history[-max_history:]
        if len(self.rtt_history) > max_history:
            self.rtt_history = self.rtt_history[-max_history:]
        
        # Check if we should adjust bitrate
        self._adjust_bitrate(packet_loss, jitter, rtt)
    
    def _adjust_bitrate(self, 
                       packet_loss: float, 
                       jitter: Optional[float] = None,
                       rtt: Optional[float] = None) -> None:
        """Adjust bitrate based on network conditions.
        
        Args:
            packet_loss: Current packet loss ratio (0.0 to 1.0)
            jitter: Network jitter in milliseconds (optional)
            rtt: Round-trip time in milliseconds (optional)
        """
        now = time.time()
        
        # Check if we're in the stability period
        if now - self.last_adjustment_time < self.stability_period:
            self.stats['stability_events'] += 1
            return
        
        # Determine if we need to adjust
        if packet_loss > self.congestion_threshold:
            # Congestion detected, reduce bitrate
            self.stats['congestion_events'] += 1
            self._decrease_bitrate(packet_loss)
        else:
            # Good conditions, potentially increase bitrate
            self._consider_increasing_bitrate(packet_loss, jitter, rtt)
        
        self.last_adjustment_time = now
    
    def _decrease_bitrate(self, packet_loss: float) -> None:
        """Decrease bitrate due to network congestion.
        
        Args:
            packet_loss: Current packet loss ratio (0.0 to 1.0)
        """
        # Calculate reduction amount based on strategy and packet loss severity
        reduction_factor = self._get_reduction_factor(packet_loss)
        reduction = int(self.step_size * reduction_factor)
        
        # Apply reduction
        new_bitrate = max(self.min_bitrate, self.current_bitrate - reduction)
        
        if new_bitrate < self.current_bitrate:
            self.stats['adjustments_down'] += 1
            self.current_bitrate = new_bitrate
            self._record_bitrate()
            self._notify_bitrate_change()
            logging.info(f"Decreased bitrate to {self.current_bitrate} bps due to packet loss {packet_loss:.2%}")
    
    def _consider_increasing_bitrate(self, 
                                    packet_loss: float, 
                                    jitter: Optional[float], 
                                    rtt: Optional[float]) -> None:
        """Consider increasing bitrate if conditions are good.
        
        Args:
            packet_loss: Current packet loss ratio (0.0 to 1.0)
            jitter: Network jitter in milliseconds (optional)
            rtt: Round-trip time in milliseconds (optional)
        """
        # Check if our strategy allows for increase
        if self.strategy == AdaptiveBitrateStrategy.AGGRESSIVE:
            # Aggressive strategy is cautious about increasing
            if packet_loss > 0.01:  # More than 1% loss
                return
        
        # Check recent history
        avg_loss = sum(self.packet_loss_history[-5:]) / min(5, len(self.packet_loss_history))
        if avg_loss > self.congestion_threshold / 2:
            # Recent history shows some loss, don't increase
            return
        
        # We can increase
        new_bitrate = min(self.max_bitrate, self.current_bitrate + self.step_size)
        
        if new_bitrate > self.current_bitrate:
            self.stats['adjustments_up'] += 1
            self.current_bitrate = new_bitrate
            self._record_bitrate()
            self._notify_bitrate_change()
            logging.info(f"Increased bitrate to {self.current_bitrate} bps")
    
    def _get_reduction_factor(self, packet_loss: float) -> float:
        """Get reduction factor based on strategy and packet loss.
        
        Args:
            packet_loss: Current packet loss ratio (0.0 to 1.0)
            
        Returns:
            Reduction factor to apply to step size
        """
        # Base factor on packet loss severity
        base_factor = min(1.0, packet_loss * 10)  # 5% loss = 0.5 factor, 10%+ loss = 1.0 factor
        
        # Adjust based on strategy
        if self.strategy == AdaptiveBitrateStrategy.QUALITY:
            # Quality strategy reduces less aggressively
            return base_factor * 1.0
        elif self.strategy == AdaptiveBitrateStrategy.BALANCED:
            # Balanced strategy is moderate
            return base_factor * 1.5
        elif self.strategy == AdaptiveBitrateStrategy.AGGRESSIVE:
            # Aggressive strategy reduces more strongly
            return base_factor * 2.0
        
        return base_factor
    
    def _record_bitrate(self) -> None:
        """Record current bitrate with timestamp."""
        self.bitrate_history.append((time.time(), self.current_bitrate))
        
        # Keep history at a reasonable size
        max_history = 100
        if len(self.bitrate_history) > max_history:
            self.bitrate_history = self.bitrate_history[-max_history:]
    
    def _notify_bitrate_change(self) -> None:
        """Notify callback about bitrate change."""
        if self.bitrate_change_callback:
            try:
                self.bitrate_change_callback(self.current_bitrate)
            except Exception as e:
                logging.error(f"Error in bitrate change callback: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get controller statistics.
        
        Returns:
            Dictionary of statistics
        """
        return {
            'current_bitrate': self.current_bitrate,
            'min_bitrate': self.min_bitrate,
            'max_bitrate': self.max_bitrate,
            'strategy': self.strategy.value,
            'adjustments_up': self.stats['adjustments_up'],
            'adjustments_down': self.stats['adjustments_down'],
            'congestion_events': self.stats['congestion_events'],
            'stability_events': self.stats['stability_events'],
            'avg_packet_loss': sum(self.packet_loss_history) / max(1, len(self.packet_loss_history)),
            'bitrate_history': self.bitrate_history[-10:],  # Last 10 entries
        }
    
    def reset(self, start_bitrate: Optional[int] = None) -> None:
        """Reset the controller state.
        
        Args:
            start_bitrate: New starting bitrate (optional)
        """
        if start_bitrate is not None:
            self.current_bitrate = min(max(start_bitrate, self.min_bitrate), self.max_bitrate)
        else:
            self.current_bitrate = min(max(DEFAULT_START_BITRATE, self.min_bitrate), self.max_bitrate)
            
        self.last_adjustment_time = 0
        self.packet_loss_history = []
        self.jitter_history = []
        self.rtt_history = []
        self.bitrate_history = []
        
        self.stats = {
            'adjustments_up': 0,
            'adjustments_down': 0,
            'congestion_events': 0,
            'stability_events': 0
        }
        
        self._record_bitrate()
        self._notify_bitrate_change() 