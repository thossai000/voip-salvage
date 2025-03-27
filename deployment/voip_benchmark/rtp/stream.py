"""
RTP Stream Implementation

This module provides an RTP stream implementation that can send
and receive audio data over RTP.
"""

import time
import threading
import logging
import queue
from typing import Optional, Tuple, List, Dict, Any, Callable, Union

from voip_benchmark.rtp.packet import RTPPacket, PAYLOAD_TYPE_OPUS
from voip_benchmark.rtp.session import RTPSession
from voip_benchmark.codecs.base import CodecBase


class RTPStream:
    """RTP stream implementation.
    
    This class provides a high-level interface for sending and receiving
    audio streams over RTP.
    """
    
    def __init__(self, 
                 session: RTPSession,
                 codec: CodecBase,
                 payload_type: int = PAYLOAD_TYPE_OPUS,
                 frame_size: int = 960,  # 20ms at 48kHz
                 jitter_buffer_size: int = 3):  # 3 frames = 60ms
        """Initialize an RTP stream.
        
        Args:
            session: RTP session to use
            codec: Audio codec to use
            payload_type: RTP payload type
            frame_size: Frame size in samples
            jitter_buffer_size: Jitter buffer size in frames
        """
        self.session = session
        self.codec = codec
        self.payload_type = payload_type
        self.frame_size = frame_size
        self.jitter_buffer_size = jitter_buffer_size
        
        # State
        self.running = False
        self.sequence_number = 0
        self.timestamp = 0
        self.ssrc = None
        
        # Jitter buffer
        self.jitter_buffer = queue.PriorityQueue()
        self.last_played_seq = -1
        
        # Callbacks
        self.frame_callback = None
        
        # Performance metrics
        self.packet_loss_count = 0
        self.late_packet_count = 0
        self.jitter_values = []
        self.last_receive_time = None
        self.last_timestamp = None
    
    def start(self) -> None:
        """Start the RTP stream."""
        if self.running:
            return
            
        self.running = True
        
        # Start receiving packets
        self.session.start_receiving(self._handle_packet)
        
        logging.debug("RTP stream started")
    
    def stop(self) -> None:
        """Stop the RTP stream."""
        if not self.running:
            return
            
        self.running = False
        
        # Stop receiving packets
        self.session.stop_receiving()
        
        # Clear jitter buffer
        while not self.jitter_buffer.empty():
            try:
                self.jitter_buffer.get_nowait()
            except:
                pass
        
        logging.debug("RTP stream stopped")
    
    def send_frame(self, frame_data: bytes) -> bool:
        """Send an audio frame.
        
        Args:
            frame_data: Raw PCM audio data for one frame
            
        Returns:
            True if the frame was sent, False otherwise
        """
        if not self.running:
            return False
            
        try:
            # Encode frame
            encoded_data = self.codec.encode(frame_data)
            
            # Create RTP packet
            packet = RTPPacket(
                payload_type=self.payload_type,
                payload=encoded_data,
                sequence_number=self.sequence_number,
                timestamp=self.timestamp,
                ssrc=self.ssrc
            )
            
            # Send packet
            result = self.session.send_packet(packet)
            
            # Update state
            self.sequence_number = (self.sequence_number + 1) & 0xFFFF
            self.timestamp += self.frame_size
            
            return result
            
        except Exception as e:
            logging.error(f"Failed to send frame: {e}")
            return False
    
    def _handle_packet(self, packet: RTPPacket, source: Tuple[str, int]) -> None:
        """Handle a received RTP packet.
        
        Args:
            packet: Received RTP packet
            source: Source address (ip, port)
        """
        if not self.running:
            return
            
        # Initialize SSRC if needed
        if self.ssrc is None:
            self.ssrc = packet.ssrc
            
        # Check if packet is from the same stream
        if packet.ssrc != self.ssrc:
            logging.warning(f"Received packet from different SSRC: {packet.ssrc} (expected {self.ssrc})")
            return
            
        # Update jitter calculation
        now = time.time()
        if self.last_receive_time is not None and self.last_timestamp is not None:
            # Calculate expected arrival time
            time_diff = now - self.last_receive_time
            timestamp_diff = packet.timestamp - self.last_timestamp
            samples_per_second = self.codec.sample_rate
            expected_time_diff = timestamp_diff / samples_per_second
            
            # Calculate jitter
            jitter = abs(time_diff - expected_time_diff) * 1000  # ms
            self.jitter_values.append(jitter)
            
        self.last_receive_time = now
        self.last_timestamp = packet.timestamp
        
        # Process packet
        try:
            # Add to jitter buffer
            self.jitter_buffer.put((packet.sequence_number, packet))
            
            # Process jitter buffer
            self._process_jitter_buffer()
            
        except Exception as e:
            logging.error(f"Error processing received packet: {e}")
    
    def _process_jitter_buffer(self) -> None:
        """Process packets in the jitter buffer."""
        # Check if we have enough packets
        if self.jitter_buffer.qsize() < self.jitter_buffer_size:
            return
            
        # Get the next packet
        try:
            seq_num, packet = self.jitter_buffer.get_nowait()
            
            # Check for missing packets
            if self.last_played_seq >= 0:
                expected_seq = (self.last_played_seq + 1) & 0xFFFF
                if seq_num != expected_seq:
                    # Calculate number of missing packets
                    if seq_num > expected_seq:
                        missing = (seq_num - expected_seq) & 0xFFFF
                    else:
                        missing = (0x10000 + seq_num - expected_seq) & 0xFFFF
                        
                    if missing > 0:
                        self.packet_loss_count += missing
                        logging.debug(f"Detected {missing} missing packet(s) (expected {expected_seq}, got {seq_num})")
            
            self.last_played_seq = seq_num
            
            # Decode payload
            try:
                decoded_data = self.codec.decode(packet.payload)
                
                # Call frame callback if set
                if self.frame_callback:
                    self.frame_callback(decoded_data, packet.timestamp)
                    
            except Exception as e:
                logging.warning(f"Failed to decode packet payload: {e}")
                
        except queue.Empty:
            pass
    
    def set_frame_callback(self, callback: Callable[[bytes, int], None]) -> None:
        """Set a callback for decoded frames.
        
        Args:
            callback: Function to call when a frame is decoded. 
                     Takes (frame_data, timestamp) as arguments.
        """
        self.frame_callback = callback
    
    def get_stats(self) -> Dict[str, Any]:
        """Get stream statistics.
        
        Returns:
            Dictionary of statistics
        """
        session_stats = self.session.get_stats()
        
        # Calculate average jitter
        avg_jitter = 0.0
        if self.jitter_values:
            avg_jitter = sum(self.jitter_values) / len(self.jitter_values)
            
        return {
            **session_stats,
            'codec': self.codec.__class__.__name__,
            'bitrate': self.codec.get_bitrate(),
            'frame_size': self.frame_size,
            'packet_loss_count': self.packet_loss_count,
            'late_packet_count': self.late_packet_count,
            'jitter_buffer_size': self.jitter_buffer_size,
            'jitter_buffer_level': self.jitter_buffer.qsize(),
            'average_jitter_ms': avg_jitter
        } 