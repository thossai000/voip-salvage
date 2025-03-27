#!/usr/bin/env python3

import time
import logging
import math
from enum import Enum

class AdaptationStrategy(Enum):
    """
    Strategies for adapting bitrate based on network conditions.
    """
    BALANCED = "balanced"
    QUALITY = "quality"
    AGGRESSIVE = "aggressive"
    
    def __str__(self):
        return self.value


class AdaptiveBitrateController:
    """
    Controls bitrate adaptation based on network conditions.
    """
    
    def __init__(self, initial_bitrate=24000, min_bitrate=8000, max_bitrate=128000,
                 strategy=AdaptationStrategy.BALANCED, measurement_window=5):
        """
        Initialize adaptive bitrate controller.
        
        Args:
            initial_bitrate: Starting bitrate in bps
            min_bitrate: Minimum allowed bitrate in bps
            max_bitrate: Maximum allowed bitrate in bps
            strategy: Bitrate adaptation strategy
            measurement_window: Window size for measurements in seconds
        """
        # Bitrate parameters
        self.current_bitrate = initial_bitrate
        self.min_bitrate = min_bitrate
        self.max_bitrate = max_bitrate
        
        # Strategy
        if isinstance(strategy, str):
            try:
                self.strategy = AdaptationStrategy(strategy)
            except ValueError:
                logging.warning(f"Unknown strategy: {strategy}. Using BALANCED.")
                self.strategy = AdaptationStrategy.BALANCED
        else:
            self.strategy = strategy
            
        # Measurement parameters
        self.measurement_window = measurement_window
        self.measurements = []
        self.last_adjustment_time = time.time()
        
        # Performance metrics
        self.packet_loss_threshold = self._get_packet_loss_threshold()
        self.jitter_threshold = self._get_jitter_threshold()
        self.rtt_threshold = self._get_rtt_threshold()
        
        # Stability parameters
        self.stability_count = 0
        self.required_stability = 3  # Minimum measurements before increasing
        
    def _get_packet_loss_threshold(self):
        """Get packet loss threshold based on strategy."""
        if self.strategy == AdaptationStrategy.BALANCED:
            return 0.05  # 5%
        elif self.strategy == AdaptationStrategy.QUALITY:
            return 0.03  # 3%
        elif self.strategy == AdaptationStrategy.AGGRESSIVE:
            return 0.10  # 10%
        return 0.05  # Default
        
    def _get_jitter_threshold(self):
        """Get jitter threshold in milliseconds based on strategy."""
        if self.strategy == AdaptationStrategy.BALANCED:
            return 30  # 30ms
        elif self.strategy == AdaptationStrategy.QUALITY:
            return 20  # 20ms
        elif self.strategy == AdaptationStrategy.AGGRESSIVE:
            return 50  # 50ms
        return 30  # Default
        
    def _get_rtt_threshold(self):
        """Get round-trip time threshold in milliseconds based on strategy."""
        if self.strategy == AdaptationStrategy.BALANCED:
            return 300  # 300ms
        elif self.strategy == AdaptationStrategy.QUALITY:
            return 200  # 200ms
        elif self.strategy == AdaptationStrategy.AGGRESSIVE:
            return 500  # 500ms
        return 300  # Default
        
    def add_measurement(self, packet_loss=0.0, jitter=0.0, rtt=0.0):
        """
        Add a new network measurement.
        
        Args:
            packet_loss: Packet loss ratio (0.0 to 1.0)
            jitter: Jitter in milliseconds
            rtt: Round-trip time in milliseconds
            
        Returns:
            New bitrate if changed, otherwise None
        """
        # Add measurement
        now = time.time()
        measurement = {
            'timestamp': now,
            'packet_loss': packet_loss,
            'jitter': jitter,
            'rtt': rtt
        }
        self.measurements.append(measurement)
        
        # Remove old measurements outside the window
        self.measurements = [m for m in self.measurements 
                            if now - m['timestamp'] <= self.measurement_window]
        
        # Check if we should adjust bitrate
        if now - self.last_adjustment_time >= 1.0:  # At most once per second
            return self._adjust_bitrate()
            
        return None
        
    def _adjust_bitrate(self):
        """
        Adjust bitrate based on measurements.
        
        Returns:
            New bitrate if changed, otherwise None
        """
        if not self.measurements:
            return None
            
        # Calculate average metrics
        avg_packet_loss = sum(m['packet_loss'] for m in self.measurements) / len(self.measurements)
        avg_jitter = sum(m['jitter'] for m in self.measurements) / len(self.measurements)
        avg_rtt = sum(m['rtt'] for m in self.measurements) / len(self.measurements)
        
        old_bitrate = self.current_bitrate
        
        # Check if network conditions are bad
        if (avg_packet_loss > self.packet_loss_threshold or
            avg_jitter > self.jitter_threshold or
            avg_rtt > self.rtt_threshold):
            
            # Decrease bitrate
            self._decrease_bitrate(avg_packet_loss, avg_jitter, avg_rtt)
            self.stability_count = 0
            
        else:
            # Network conditions are good
            self.stability_count += 1
            
            # Only increase after sufficient stability
            if self.stability_count >= self.required_stability:
                self._increase_bitrate()
                self.stability_count = 0
        
        # Update last adjustment time
        self.last_adjustment_time = time.time()
        
        # Return new bitrate if changed
        if self.current_bitrate != old_bitrate:
            logging.info(f"Bitrate adjusted: {old_bitrate} -> {self.current_bitrate} bps")
            return self.current_bitrate
            
        return None
        
    def _decrease_bitrate(self, packet_loss, jitter, rtt):
        """
        Decrease bitrate based on network conditions.
        
        Args:
            packet_loss: Current packet loss ratio
            jitter: Current jitter in milliseconds
            rtt: Current round-trip time in milliseconds
        """
        # Calculate severity of issues
        pl_severity = min(1.0, packet_loss / (2 * self.packet_loss_threshold))
        jitter_severity = min(1.0, jitter / (2 * self.jitter_threshold))
        rtt_severity = min(1.0, rtt / (2 * self.rtt_threshold))
        
        # Combined severity
        severity = max(pl_severity, jitter_severity, rtt_severity)
        
        # Determine decrease factor
        if self.strategy == AdaptationStrategy.BALANCED:
            decrease_factor = 0.8 - (0.2 * severity)
        elif self.strategy == AdaptationStrategy.QUALITY:
            decrease_factor = 0.9 - (0.1 * severity)
        else:  # AGGRESSIVE
            decrease_factor = 0.5 - (0.3 * severity)
            
        # Apply decrease
        new_bitrate = max(self.min_bitrate, 
                         int(self.current_bitrate * decrease_factor))
        
        self.current_bitrate = new_bitrate
        
    def _increase_bitrate(self):
        """Increase bitrate gradually."""
        # Determine increase step
        if self.strategy == AdaptationStrategy.BALANCED:
            # Additive increase: Add 10% of the gap to max
            gap = self.max_bitrate - self.current_bitrate
            increase = max(1000, int(gap * 0.1))
        elif self.strategy == AdaptationStrategy.QUALITY:
            # Conservative increase: Add 5% of the gap to max
            gap = self.max_bitrate - self.current_bitrate
            increase = max(500, int(gap * 0.05))
        else:  # AGGRESSIVE
            # Multiplicative increase: 20% increase
            increase = int(self.current_bitrate * 0.2)
            
        # Apply increase
        new_bitrate = min(self.max_bitrate, 
                         self.current_bitrate + increase)
        
        self.current_bitrate = new_bitrate
        
    def get_current_bitrate(self):
        """Get current bitrate in bps."""
        return self.current_bitrate
        
    def set_strategy(self, strategy):
        """
        Set adaptation strategy.
        
        Args:
            strategy: New strategy (string or AdaptationStrategy enum)
            
        Returns:
            True if strategy was changed, False otherwise
        """
        if isinstance(strategy, str):
            try:
                new_strategy = AdaptationStrategy(strategy)
            except ValueError:
                logging.warning(f"Unknown strategy: {strategy}")
                return False
        else:
            new_strategy = strategy
            
        if new_strategy != self.strategy:
            self.strategy = new_strategy
            
            # Update thresholds
            self.packet_loss_threshold = self._get_packet_loss_threshold()
            self.jitter_threshold = self._get_jitter_threshold()
            self.rtt_threshold = self._get_rtt_threshold()
            
            return True
            
        return False


class NetworkMonitor:
    """
    Monitors network conditions for adaptive bitrate control.
    """
    
    def __init__(self, window_size=100):
        """
        Initialize network monitor.
        
        Args:
            window_size: Maximum number of packets to consider
        """
        self.window_size = window_size
        self.packets = []  # List of packet info dictionaries
        self.expected_seq = None
        
    def add_packet(self, seq_num, timestamp, size):
        """
        Add a received packet to the monitor.
        
        Args:
            seq_num: Packet sequence number
            timestamp: Receive timestamp
            size: Packet size in bytes
        """
        # Initialize expected_seq if this is the first packet
        if self.expected_seq is None:
            self.expected_seq = seq_num
            
        packet_info = {
            'seq_num': seq_num,
            'timestamp': timestamp,
            'size': size,
            'expected': self.expected_seq == seq_num
        }
        
        self.packets.append(packet_info)
        
        # Update expected sequence number
        self.expected_seq = (seq_num + 1) % 65536
        
        # Trim packet history if needed
        if len(self.packets) > self.window_size:
            self.packets = self.packets[-self.window_size:]
            
    def get_packet_loss(self):
        """
        Calculate packet loss ratio.
        
        Returns:
            Packet loss ratio (0.0 to 1.0)
        """
        if not self.packets:
            return 0.0
            
        # Count unexpected packets
        unexpected = sum(1 for p in self.packets if not p['expected'])
        
        # Estimate total expected packets from sequence numbers
        if len(self.packets) >= 2:
            first_seq = self.packets[0]['seq_num']
            last_seq = self.packets[-1]['seq_num']
            
            # Handle sequence number wraparound
            if last_seq < first_seq:
                last_seq += 65536
                
            expected_count = last_seq - first_seq + 1
            return unexpected / expected_count
            
        return 0.0
        
    def get_jitter(self):
        """
        Calculate average jitter in milliseconds.
        
        Returns:
            Average jitter in milliseconds
        """
        if len(self.packets) < 2:
            return 0.0
            
        # Calculate inter-arrival times
        intervals = []
        for i in range(1, len(self.packets)):
            interval = self.packets[i]['timestamp'] - self.packets[i-1]['timestamp']
            intervals.append(interval * 1000)  # Convert to milliseconds
            
        if not intervals:
            return 0.0
            
        # Calculate mean interval
        mean_interval = sum(intervals) / len(intervals)
        
        # Calculate jitter (deviation from mean)
        jitter = sum(abs(i - mean_interval) for i in intervals) / len(intervals)
        
        return jitter
        
    def get_stats(self):
        """
        Get network statistics.
        
        Returns:
            Dictionary with network statistics
        """
        packet_loss = self.get_packet_loss()
        jitter = self.get_jitter()
        
        stats = {
            'packet_count': len(self.packets),
            'packet_loss': packet_loss,
            'jitter_ms': jitter,
        }
        
        # Add bitrate if we have enough packets
        if len(self.packets) >= 2:
            duration = self.packets[-1]['timestamp'] - self.packets[0]['timestamp']
            if duration > 0:
                total_bytes = sum(p['size'] for p in self.packets)
                bitrate = (total_bytes * 8) / duration
                stats['bitrate_bps'] = bitrate
                
        return stats


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Adaptive bitrate utilities")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Simulate command
    simulate_parser = subparsers.add_parser("simulate", help="Simulate bitrate adaptation")
    simulate_parser.add_argument("--initial", type=int, default=24000, 
                                help="Initial bitrate in bps")
    simulate_parser.add_argument("--min", type=int, default=8000, 
                                help="Minimum bitrate in bps")
    simulate_parser.add_argument("--max", type=int, default=128000, 
                                help="Maximum bitrate in bps")
    simulate_parser.add_argument("--strategy", choices=["balanced", "quality", "aggressive"], 
                                default="balanced", help="Adaptation strategy")
    
    args = parser.parse_args()
    
    if args.command == "simulate":
        # Set up logging
        logging.basicConfig(level=logging.INFO, 
                           format='%(asctime)s - %(levelname)s - %(message)s')
        
        # Create controller
        controller = AdaptiveBitrateController(
            initial_bitrate=args.initial,
            min_bitrate=args.min,
            max_bitrate=args.max,
            strategy=args.strategy
        )
        
        print(f"Simulating bitrate adaptation with {args.strategy} strategy")
        print(f"Initial bitrate: {args.initial} bps")
        
        # Simulation
        t = 0
        while t < 60:  # 60 seconds
            # Network conditions vary over time
            if t < 10:
                # Good conditions initially
                packet_loss = 0.01
                jitter = 10
                rtt = 100
            elif t < 20:
                # Conditions start to degrade
                packet_loss = 0.03
                jitter = 25
                rtt = 200
            elif t < 30:
                # Poor conditions
                packet_loss = 0.08
                jitter = 50
                rtt = 400
            elif t < 40:
                # Very poor conditions
                packet_loss = 0.15
                jitter = 100
                rtt = 600
            elif t < 50:
                # Conditions improve
                packet_loss = 0.04
                jitter = 30
                rtt = 250
            else:
                # Good conditions again
                packet_loss = 0.01
                jitter = 15
                rtt = 120
                
            # Add some random variation
            import random
            packet_loss += random.uniform(-0.01, 0.01)
            packet_loss = max(0, min(1, packet_loss))
            jitter += random.uniform(-5, 5)
            jitter = max(0, jitter)
            rtt += random.uniform(-20, 20)
            rtt = max(0, rtt)
            
            # Add measurement
            new_bitrate = controller.add_measurement(packet_loss, jitter, rtt)
            
            print(f"Time {t:2d}s: PL={packet_loss:.2f}, Jitter={jitter:.1f}ms, RTT={rtt:.0f}ms, "
                  f"Bitrate={controller.get_current_bitrate():,} bps")
            
            t += 1
            time.sleep(0.1)  # Speed up simulation 