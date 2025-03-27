"""
RTP Stream Implementation

This module provides functionality for handling continuous audio
streams over RTP, including packetization, jitter buffering, and
stream management.
"""

import time
import threading
import queue
import logging
from typing import Optional, Dict, List, Tuple, Callable, Any, Union

from voip_benchmark.rtp.packet import RTPPacket
from voip_benchmark.rtp.session import RTPSession
from voip_benchmark.codecs.base import CodecBase


# Default RTP stream settings
DEFAULT_JITTER_BUFFER_SIZE = 10  # Max number of packets in jitter buffer
DEFAULT_PACKET_DURATION_MS = 20  # 20ms per packet
DEFAULT_BUFFERING_TIME_MS = 60   # 60ms initial buffering time


class JitterBuffer:
    """Jitter buffer implementation.
    
    This class provides a simple jitter buffer for handling network jitter,
    packet reordering, and packet loss.
    """
    
    def __init__(self, max_size: int = DEFAULT_JITTER_BUFFER_SIZE):
        """Initialize the jitter buffer.
        
        Args:
            max_size: Maximum number of packets in the buffer
        """
        self.max_size = max_size
        self.buffer = {}  # Dictionary mapping sequence numbers to packets
        self.next_sequence = None  # Next expected sequence number
        
        # Statistics
        self.packets_added = 0
        self.packets_retrieved = 0
        self.packets_dropped = 0
        self.out_of_order_packets = 0
        
        # Logger
        self.logger = logging.getLogger('voip_benchmark.rtp.jitter_buffer')
    
    def add_packet(self, packet: RTPPacket) -> None:
        """Add a packet to the jitter buffer.
        
        Args:
            packet: RTP packet to add
        """
        # If buffer is empty, initialize next_sequence
        if self.next_sequence is None:
            self.next_sequence = packet.sequence_number
        
        # Check if packet is too old (already played or dropped)
        if self._is_packet_too_old(packet.sequence_number):
            self.packets_dropped += 1
            self.logger.debug(f"Dropping old packet {packet.sequence_number} (next expected: {self.next_sequence})")
            return
        
        # Check if buffer is full
        if len(self.buffer) >= self.max_size:
            # Remove oldest packet if buffer is full
            oldest_seq = min(self.buffer.keys())
            if oldest_seq < packet.sequence_number:
                del self.buffer[oldest_seq]
                self.packets_dropped += 1
                self.logger.debug(f"Buffer full, dropping oldest packet {oldest_seq}")
            else:
                self.packets_dropped += 1
                self.logger.debug(f"Buffer full, dropping new packet {packet.sequence_number}")
                return
        
        # Add packet to buffer
        self.buffer[packet.sequence_number] = packet
        self.packets_added += 1
        
        # Check if packet is out of order
        if packet.sequence_number < self.next_sequence:
            self.out_of_order_packets += 1
            self.logger.debug(f"Out of order packet {packet.sequence_number} (next expected: {self.next_sequence})")
    
    def get_next_packet(self) -> Optional[RTPPacket]:
        """Get the next packet from the jitter buffer.
        
        Returns:
            Next packet or None if no packet is available
        """
        if not self.buffer or self.next_sequence is None:
            return None
        
        # Check if next packet is available
        if self.next_sequence in self.buffer:
            packet = self.buffer.pop(self.next_sequence)
            self.next_sequence = (self.next_sequence + 1) & 0xFFFF
            self.packets_retrieved += 1
            return packet
        
        # Calculate sequence number distance to determine if we should wait
        min_seq = min(self.buffer.keys())
        if self._sequence_distance(self.next_sequence, min_seq) > self.max_size:
            # We've probably missed too many packets, skip to the next available
            old_next = self.next_sequence
            self.next_sequence = min_seq
            self.logger.debug(f"Skipping missing packets from {old_next} to {min_seq}")
            return self.get_next_packet()
        
        return None
    
    def clear(self) -> None:
        """Clear the jitter buffer."""
        self.buffer.clear()
        self.next_sequence = None
    
    def _is_packet_too_old(self, sequence_number: int) -> bool:
        """Check if a packet is too old to be added to the buffer.
        
        Args:
            sequence_number: Packet sequence number
            
        Returns:
            True if the packet is too old, False otherwise
        """
        if self.next_sequence is None:
            return False
            
        # Calculate sequence number distance (handles wrapping)
        distance = self._sequence_distance(sequence_number, self.next_sequence)
        
        # If the packet is more than half the sequence space behind,
        # it's probably new (due to wrap-around)
        if distance > 32768:  # Half of 16-bit sequence space
            return False
            
        return sequence_number < self.next_sequence
    
    def _sequence_distance(self, seq1: int, seq2: int) -> int:
        """Calculate the distance between two sequence numbers.
        
        This handles sequence number wrapping.
        
        Args:
            seq1: First sequence number
            seq2: Second sequence number
            
        Returns:
            Distance between the sequence numbers
        """
        diff = (seq1 - seq2) & 0xFFFF  # 16-bit unsigned
        if diff > 32768:  # Half of 16-bit sequence space
            diff = 65536 - diff
        return diff
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the jitter buffer.
        
        Returns:
            Dictionary containing jitter buffer statistics
        """
        return {
            'buffer_size': len(self.buffer),
            'max_size': self.max_size,
            'packets_added': self.packets_added,
            'packets_retrieved': self.packets_retrieved,
            'packets_dropped': self.packets_dropped,
            'out_of_order_packets': self.out_of_order_packets,
            'next_sequence': self.next_sequence
        }


class RTPStream:
    """RTP stream implementation.
    
    This class provides functionality for handling continuous audio
    streams over RTP, including packetization, jitter buffering, and
    stream management.
    """
    
    def __init__(self, 
                 session: RTPSession,
                 codec: Optional[CodecBase] = None,
                 payload_type: int = 0,
                 frame_size: int = 960,  # 20ms at 48kHz
                 jitter_buffer_size: int = DEFAULT_JITTER_BUFFER_SIZE):
        """Initialize an RTP stream.
        
        Args:
            session: RTP session for sending/receiving packets
            codec: Audio codec for encoding/decoding (None for raw PCM)
            payload_type: RTP payload type
            frame_size: Audio frame size in samples
            jitter_buffer_size: Maximum number of packets in jitter buffer
        """
        self.session = session
        self.codec = codec
        self.payload_type = payload_type
        self.frame_size = frame_size
        
        # Initialize jitter buffer
        self.jitter_buffer = JitterBuffer(max_size=jitter_buffer_size)
        
        # Initialize streaming state
        self.streaming = False
        self.send_thread = None
        self.receive_thread = None
        self.send_queue = queue.Queue()
        self.receive_queue = queue.Queue()
        self.stop_event = threading.Event()
        
        # Initialize callbacks
        self.on_frame_received = None
        
        # Timestamp handling
        self.timestamp_increment = frame_size  # One frame
        
        # Logger
        self.logger = logging.getLogger('voip_benchmark.rtp.stream')
    
    def start_streaming(self, on_frame_received: Optional[Callable[[bytes], None]] = None) -> None:
        """Start streaming audio.
        
        Args:
            on_frame_received: Callback function called when a frame is received
            
        Raises:
            RuntimeError: If already streaming or session not open
        """
        if self.streaming:
            raise RuntimeError("Already streaming")
            
        if not self.session.socket:
            raise RuntimeError("RTP session not open")
            
        self.on_frame_received = on_frame_received
        self.streaming = True
        self.stop_event.clear()
        
        # Start session receiving if it's not already running
        self.session.start_receiving(self._handle_packet)
        
        # Start receive thread
        self.receive_thread = threading.Thread(target=self._receive_loop)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        
        self.logger.info("Started RTP streaming")
    
    def stop_streaming(self) -> None:
        """Stop streaming audio."""
        if not self.streaming:
            return
            
        self.streaming = False
        self.stop_event.set()
        
        # Clear queues
        while not self.send_queue.empty():
            try:
                self.send_queue.get_nowait()
            except queue.Empty:
                pass
                
        while not self.receive_queue.empty():
            try:
                self.receive_queue.get_nowait()
            except queue.Empty:
                pass
        
        # Stop send thread if running
        if self.send_thread and self.send_thread.is_alive():
            self.send_thread.join(timeout=2.0)
            self.send_thread = None
        
        # Stop receive thread if running
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=2.0)
            self.receive_thread = None
        
        # Clear jitter buffer
        self.jitter_buffer.clear()
        
        self.logger.info("Stopped RTP streaming")
    
    def send_audio(self, audio_data: bytes, blocking: bool = False) -> None:
        """Send audio data.
        
        The audio data will be packetized and sent as RTP packets.
        
        Args:
            audio_data: Raw audio data to send
            blocking: Whether to block until all data is sent
            
        Raises:
            RuntimeError: If not streaming
            queue.Full: If the send queue is full and blocking is False
        """
        if not self.streaming:
            raise RuntimeError("Not streaming")
        
        # Start send thread if it's not running
        if not self.send_thread or not self.send_thread.is_alive():
            self.send_thread = threading.Thread(target=self._send_loop)
            self.send_thread.daemon = True
            self.send_thread.start()
        
        # Add audio data to send queue
        if blocking:
            self.send_queue.put(audio_data)
        else:
            try:
                self.send_queue.put_nowait(audio_data)
            except queue.Full:
                self.logger.warning("Send queue full, dropping audio data")
                raise
    
    def _send_loop(self) -> None:
        """Main send loop."""
        while self.streaming and not self.stop_event.is_set():
            try:
                # Get audio data from send queue with timeout
                audio_data = self.send_queue.get(timeout=0.1)
                
                # Encode audio data if codec is set
                if self.codec:
                    encoded_data = self.codec.encode(audio_data)
                else:
                    encoded_data = audio_data
                
                # Send packet
                bytes_sent = self.session.send_packet(
                    payload=encoded_data,
                    payload_type=self.payload_type
                )
                
                self.logger.debug(f"Sent {bytes_sent} bytes")
                
                # Update session timestamp for next packet
                self.session.timestamp = (self.session.timestamp + self.timestamp_increment) & 0xFFFFFFFF
                
                # Mark queue item as done
                self.send_queue.task_done()
                
            except queue.Empty:
                # Queue empty, just continue the loop
                pass
                
            except Exception as e:
                self.logger.error(f"Error sending audio data: {e}")
                if not self.streaming:
                    break
    
    def _handle_packet(self, packet: RTPPacket) -> None:
        """Handle a received RTP packet.
        
        Args:
            packet: RTP packet
        """
        # Add packet to jitter buffer
        self.jitter_buffer.add_packet(packet)
    
    def _receive_loop(self) -> None:
        """Main receive loop."""
        # Initial buffering
        time.sleep(DEFAULT_BUFFERING_TIME_MS / 1000.0)
        
        while self.streaming and not self.stop_event.is_set():
            try:
                # Get next packet from jitter buffer
                packet = self.jitter_buffer.get_next_packet()
                
                if packet:
                    # Decode payload if codec is set
                    if self.codec and packet.payload:
                        try:
                            decoded_data = self.codec.decode(packet.payload)
                        except Exception as e:
                            self.logger.error(f"Error decoding packet payload: {e}")
                            continue
                    else:
                        decoded_data = packet.payload
                    
                    # Add decoded data to receive queue
                    self.receive_queue.put(decoded_data)
                    
                    # Call frame received callback if set
                    if self.on_frame_received:
                        try:
                            self.on_frame_received(decoded_data)
                        except Exception as e:
                            self.logger.error(f"Error in frame received callback: {e}")
                
                # Sleep for a short time to simulate real-time processing
                time.sleep(0.005)  # 5ms
                
            except Exception as e:
                self.logger.error(f"Error in receive loop: {e}")
                if not self.streaming:
                    break
    
    def get_next_frame(self, timeout: Optional[float] = None) -> Optional[bytes]:
        """Get the next audio frame from the receive queue.
        
        Args:
            timeout: Timeout in seconds for waiting for a frame
            
        Returns:
            Audio frame or None if timeout occurred
            
        Raises:
            RuntimeError: If not streaming
        """
        if not self.streaming:
            raise RuntimeError("Not streaming")
            
        try:
            return self.receive_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the RTP stream.
        
        Returns:
            Dictionary containing stream statistics
        """
        session_stats = self.session.get_stats()
        jitter_buffer_stats = self.jitter_buffer.get_stats()
        
        return {
            'session': session_stats,
            'jitter_buffer': jitter_buffer_stats,
            'send_queue_size': self.send_queue.qsize(),
            'receive_queue_size': self.receive_queue.qsize(),
            'streaming': self.streaming
        } 