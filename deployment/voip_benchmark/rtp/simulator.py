"""
RTP Network Simulator

This module provides functionality for simulating network conditions
such as packet loss, jitter, and latency for RTP traffic testing.
"""

import time
import random
import queue
import threading
import logging
from typing import List, Dict, Any, Optional, Callable, Tuple

from voip_benchmark.rtp.packet import RTPPacket


class NetworkConditions:
    """Network condition parameters for simulation."""
    
    def __init__(self, 
                packet_loss: float = 0.0,
                jitter: float = 0.0,
                latency: float = 0.0,
                duplicate: float = 0.0,
                out_of_order: float = 0.0,
                corrupt: float = 0.0):
        """Initialize network conditions.
        
        Args:
            packet_loss: Packet loss probability (0.0 to 1.0)
            jitter: Jitter in milliseconds
            latency: Additional latency in milliseconds
            duplicate: Packet duplication probability (0.0 to 1.0)
            out_of_order: Probability of packets being out of order (0.0 to 1.0)
            corrupt: Probability of packet corruption (0.0 to 1.0)
        """
        self.packet_loss = max(0.0, min(1.0, packet_loss))
        self.jitter = max(0.0, jitter)
        self.latency = max(0.0, latency)
        self.duplicate = max(0.0, min(1.0, duplicate))
        self.out_of_order = max(0.0, min(1.0, out_of_order))
        self.corrupt = max(0.0, min(1.0, corrupt))
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary.
        
        Returns:
            Dictionary representation of network conditions
        """
        return {
            'packet_loss': self.packet_loss,
            'jitter': self.jitter,
            'latency': self.latency,
            'duplicate': self.duplicate,
            'out_of_order': self.out_of_order,
            'corrupt': self.corrupt
        }


class PacketEvent:
    """Event representing a scheduled packet delivery."""
    
    def __init__(self, 
                packet: RTPPacket,
                delivery_time: float,
                is_duplicate: bool = False,
                is_corrupted: bool = False):
        """Initialize a packet event.
        
        Args:
            packet: RTP packet
            delivery_time: Scheduled delivery time (Unix timestamp)
            is_duplicate: Whether this is a duplicate packet
            is_corrupted: Whether this packet is corrupted
        """
        self.packet = packet
        self.delivery_time = delivery_time
        self.is_duplicate = is_duplicate
        self.is_corrupted = is_corrupted
    
    def __lt__(self, other: 'PacketEvent') -> bool:
        """Compare events by delivery time for priority queue."""
        return self.delivery_time < other.delivery_time


class NetworkSimulator:
    """Simulates network conditions for RTP traffic."""
    
    def __init__(self, 
                network_conditions: Optional[NetworkConditions] = None,
                packet_callback: Optional[Callable[[RTPPacket, bool, bool], None]] = None):
        """Initialize the network simulator.
        
        Args:
            network_conditions: Network conditions for simulation
            packet_callback: Callback function for delivered packets
        """
        self.conditions = network_conditions or NetworkConditions()
        self.packet_callback = packet_callback
        
        # Event queue for scheduled packet deliveries
        self.event_queue: queue.PriorityQueue[PacketEvent] = queue.PriorityQueue()
        
        # Statistics
        self.stats = {
            'packets_processed': 0,
            'packets_dropped': 0,
            'packets_delivered': 0,
            'packets_duplicated': 0,
            'packets_corrupted': 0,
            'packets_delayed': 0,
            'packets_reordered': 0,
            'start_time': 0.0,
            'end_time': 0.0,
        }
        
        # State
        self.running = False
        self.delivery_thread = None
        self.last_packet_seq = -1
    
    def set_network_conditions(self, conditions: NetworkConditions) -> None:
        """Set network conditions.
        
        Args:
            conditions: New network conditions
        """
        self.conditions = conditions
    
    def set_packet_callback(self, callback: Callable[[RTPPacket, bool, bool], None]) -> None:
        """Set packet delivery callback.
        
        Args:
            callback: Function to call when a packet is delivered.
                     Takes (packet, is_duplicate, is_corrupted) as arguments.
        """
        self.packet_callback = callback
    
    def start(self) -> None:
        """Start the network simulator."""
        if self.running:
            return
        
        self.running = True
        self.stats['start_time'] = time.time()
        
        # Start delivery thread
        self.delivery_thread = threading.Thread(target=self._delivery_loop)
        self.delivery_thread.daemon = True
        self.delivery_thread.start()
        
        logging.debug("Network simulator started")
    
    def stop(self) -> None:
        """Stop the network simulator."""
        if not self.running:
            return
        
        self.running = False
        self.stats['end_time'] = time.time()
        
        # Wait for delivery thread to finish
        if self.delivery_thread and self.delivery_thread.is_alive():
            self.delivery_thread.join(1.0)
        
        # Clear event queue
        while not self.event_queue.empty():
            try:
                self.event_queue.get_nowait()
                self.event_queue.task_done()
            except queue.Empty:
                break
        
        logging.debug("Network simulator stopped")
    
    def process_packet(self, packet: RTPPacket) -> bool:
        """Process an RTP packet through the network simulator.
        
        Args:
            packet: RTP packet to process
            
        Returns:
            True if the packet was scheduled for delivery, False if dropped
        """
        if not self.running:
            return False
        
        self.stats['packets_processed'] += 1
        
        # Check for packet loss
        if random.random() < self.conditions.packet_loss:
            self.stats['packets_dropped'] += 1
            logging.debug(f"Packet dropped: seq={packet.sequence_number}")
            return False
        
        # Calculate delivery time with latency and jitter
        now = time.time()
        latency_ms = self.conditions.latency
        
        # Add jitter if enabled
        if self.conditions.jitter > 0:
            # Random jitter between -jitter and +jitter
            jitter_ms = random.uniform(-self.conditions.jitter, self.conditions.jitter)
            latency_ms += jitter_ms
            
            if jitter_ms != 0:
                self.stats['packets_delayed'] += 1
        
        # Ensure latency is not negative
        latency_ms = max(0, latency_ms)
        delivery_time = now + (latency_ms / 1000.0)
        
        # Check for packet reordering
        if (random.random() < self.conditions.out_of_order and 
            packet.sequence_number > self.last_packet_seq):
            # Add extra delay to cause reordering
            delivery_time += (random.uniform(50, 200) / 1000.0)  # 50-200ms extra delay
            self.stats['packets_reordered'] += 1
            logging.debug(f"Packet reordered: seq={packet.sequence_number}")
        
        # Check for packet corruption
        is_corrupted = random.random() < self.conditions.corrupt
        if is_corrupted:
            self.stats['packets_corrupted'] += 1
            logging.debug(f"Packet corrupted: seq={packet.sequence_number}")
        
        # Schedule packet delivery
        event = PacketEvent(packet, delivery_time, False, is_corrupted)
        self.event_queue.put(event)
        
        # Check for packet duplication
        if random.random() < self.conditions.duplicate:
            # Schedule duplicate delivery with slightly different timing
            duplicate_delivery_time = delivery_time + (random.uniform(1, 5) / 1000.0)  # 1-5ms after original
            duplicate_event = PacketEvent(packet, duplicate_delivery_time, True, is_corrupted)
            self.event_queue.put(duplicate_event)
            self.stats['packets_duplicated'] += 1
            logging.debug(f"Packet duplicated: seq={packet.sequence_number}")
        
        # Update last packet sequence number
        self.last_packet_seq = packet.sequence_number
        
        return True
    
    def _delivery_loop(self) -> None:
        """Loop for delivering packets according to schedule."""
        while self.running:
            try:
                # Check if there are events to process
                if self.event_queue.empty():
                    time.sleep(0.001)  # 1ms sleep to avoid busy wait
                    continue
                
                # Peek at the next event
                event = self.event_queue.queue[0]
                
                # Check if it's time to deliver
                now = time.time()
                if event.delivery_time <= now:
                    # Remove from queue
                    self.event_queue.get_nowait()
                    self.event_queue.task_done()
                    
                    # Deliver the packet
                    self._deliver_packet(event.packet, event.is_duplicate, event.is_corrupted)
                else:
                    # Sleep until next delivery time (or 10ms max)
                    sleep_time = min(event.delivery_time - now, 0.01)
                    time.sleep(sleep_time)
            
            except IndexError:
                # Queue was empty when we tried to peek
                time.sleep(0.001)
            except Exception as e:
                logging.error(f"Error in network simulator delivery loop: {e}")
                time.sleep(0.01)
    
    def _deliver_packet(self, packet: RTPPacket, is_duplicate: bool, is_corrupted: bool) -> None:
        """Deliver a packet to the callback.
        
        Args:
            packet: RTP packet to deliver
            is_duplicate: Whether this is a duplicate packet
            is_corrupted: Whether this packet is corrupted
        """
        if not self.running:
            return
        
        self.stats['packets_delivered'] += 1
        
        # If packet is corrupted, modify it
        if is_corrupted:
            # Corrupt random bytes in the payload
            payload = bytearray(packet.payload)
            if payload:
                # Corrupt 1-3 bytes
                num_corruptions = random.randint(1, min(3, len(payload)))
                for _ in range(num_corruptions):
                    pos = random.randint(0, len(payload) - 1)
                    payload[pos] = random.randint(0, 255)
                packet.payload = bytes(payload)
        
        # Call callback if set
        if self.packet_callback:
            try:
                self.packet_callback(packet, is_duplicate, is_corrupted)
            except Exception as e:
                logging.error(f"Error in packet delivery callback: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get simulator statistics.
        
        Returns:
            Dictionary with simulator statistics
        """
        # Update elapsed time if simulator is running
        elapsed = 0.0
        if self.stats['start_time'] > 0:
            end_time = self.stats['end_time'] if self.stats['end_time'] > 0 else time.time()
            elapsed = end_time - self.stats['start_time']
        
        return {
            'packets_processed': self.stats['packets_processed'],
            'packets_dropped': self.stats['packets_dropped'],
            'packets_delivered': self.stats['packets_delivered'],
            'packets_duplicated': self.stats['packets_duplicated'],
            'packets_corrupted': self.stats['packets_corrupted'],
            'packets_delayed': self.stats['packets_delayed'],
            'packets_reordered': self.stats['packets_reordered'],
            'drop_rate': self.stats['packets_dropped'] / max(1, self.stats['packets_processed']),
            'delivery_rate': self.stats['packets_delivered'] / max(1, self.stats['packets_processed']),
            'elapsed_time': elapsed,
            'current_queue_size': self.event_queue.qsize(),
            'network_conditions': self.conditions.to_dict()
        } 