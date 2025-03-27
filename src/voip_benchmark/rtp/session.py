"""
RTP Session Implementation

This module provides functionality for managing RTP sessions,
including packet transmission and reception.
"""

import socket
import random
import time
import threading
import logging
from typing import Optional, Dict, List, Tuple, Callable, Any

from voip_benchmark.rtp.packet import RTPPacket

# Default RTP session settings
DEFAULT_RTP_PORT = 12345
DEFAULT_RTCP_PORT = 12346  # Typically RTP port + 1
DEFAULT_BUFFER_SIZE = 4096  # 4 KB buffer for socket operations
DEFAULT_TIMEOUT = 0.5  # 500 ms socket timeout


class RTPSession:
    """RTP session implementation.
    
    This class provides functionality for managing RTP sessions,
    including packet transmission and reception.
    """
    
    def __init__(self, 
                 local_address: str = '0.0.0.0',
                 local_port: int = DEFAULT_RTP_PORT,
                 remote_address: Optional[str] = None,
                 remote_port: Optional[int] = None,
                 ssrc: Optional[int] = None):
        """Initialize an RTP session.
        
        Args:
            local_address: Local IP address to bind to
            local_port: Local port to bind to
            remote_address: Remote IP address for sending packets (None for receive-only)
            remote_port: Remote port for sending packets (None for receive-only)
            ssrc: Synchronization source identifier (auto-generated if None)
        """
        self.local_address = local_address
        self.local_port = local_port
        self.remote_address = remote_address
        self.remote_port = remote_port
        
        # Generate SSRC if not provided
        if ssrc is None:
            self.ssrc = random.randint(0, 0xFFFFFFFF)
        else:
            self.ssrc = ssrc & 0xFFFFFFFF  # 32 bits
        
        # Initialize socket
        self.socket = None
        
        # Initialize sequence number and timestamp
        self.sequence_number = random.randint(0, 0xFFFF)
        self.timestamp = random.randint(0, 0xFFFFFFFF)
        
        # Initialize packet counters
        self.packets_sent = 0
        self.packets_received = 0
        self.bytes_sent = 0
        self.bytes_received = 0
        
        # Threading control
        self.running = False
        self.receive_thread = None
        self.stop_event = threading.Event()
        
        # Packet handler callback
        self.packet_handler = None
        
        # Logger
        self.logger = logging.getLogger('voip_benchmark.rtp.session')
    
    def open(self) -> None:
        """Open the RTP session.
        
        Creates and binds the UDP socket for the RTP session.
        
        Raises:
            socket.error: If the socket cannot be created or bound
        """
        if self.socket:
            self.close()
        
        # Create UDP socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(DEFAULT_TIMEOUT)
        
        # Bind to local address and port
        self.socket.bind((self.local_address, self.local_port))
        
        self.logger.info(f"RTP session opened on {self.local_address}:{self.local_port}")
    
    def close(self) -> None:
        """Close the RTP session.
        
        Closes the UDP socket and stops the receive thread if running.
        """
        self.stop_receiving()
        
        if self.socket:
            self.socket.close()
            self.socket = None
            
        self.logger.info("RTP session closed")
    
    def set_remote_endpoint(self, address: str, port: int) -> None:
        """Set the remote endpoint for sending packets.
        
        Args:
            address: Remote IP address
            port: Remote port
        """
        self.remote_address = address
        self.remote_port = port
        
        self.logger.info(f"Remote endpoint set to {address}:{port}")
    
    def start_receiving(self, packet_handler: Callable[[RTPPacket], None]) -> None:
        """Start receiving RTP packets.
        
        Args:
            packet_handler: Callback function to handle received packets
            
        Raises:
            RuntimeError: If the session is not open or already receiving
        """
        if not self.socket:
            raise RuntimeError("RTP session not open")
            
        if self.running:
            raise RuntimeError("Already receiving packets")
            
        self.packet_handler = packet_handler
        self.running = True
        self.stop_event.clear()
        
        # Start receive thread
        self.receive_thread = threading.Thread(target=self._receive_loop)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        
        self.logger.info("Started receiving RTP packets")
    
    def stop_receiving(self) -> None:
        """Stop receiving RTP packets."""
        if not self.running:
            return
            
        self.running = False
        self.stop_event.set()
        
        if self.receive_thread:
            self.receive_thread.join(timeout=2.0)
            self.receive_thread = None
            
        self.logger.info("Stopped receiving RTP packets")
    
    def send_packet(self, payload: bytes, payload_type: int = 0, marker: bool = False) -> int:
        """Send an RTP packet.
        
        Args:
            payload: Packet payload data
            payload_type: RTP payload type
            marker: Marker bit
            
        Returns:
            Number of bytes sent
            
        Raises:
            RuntimeError: If the session is not open or remote endpoint not set
        """
        if not self.socket:
            raise RuntimeError("RTP session not open")
            
        if not self.remote_address or not self.remote_port:
            raise RuntimeError("Remote endpoint not set")
        
        # Create packet
        packet = RTPPacket(
            payload_type=payload_type,
            payload=payload,
            sequence_number=self.sequence_number,
            timestamp=self.timestamp,
            ssrc=self.ssrc,
            marker=marker
        )
        
        # Convert to bytes
        packet_data = packet.to_bytes()
        
        # Send packet
        bytes_sent = self.socket.sendto(packet_data, (self.remote_address, self.remote_port))
        
        # Update sequence number and timestamp
        self.sequence_number = (self.sequence_number + 1) & 0xFFFF
        
        # Update counters
        self.packets_sent += 1
        self.bytes_sent += bytes_sent
        
        return bytes_sent
    
    def _receive_loop(self) -> None:
        """Main receive loop."""
        if not self.socket:
            return
            
        while self.running and not self.stop_event.is_set():
            try:
                # Receive packet
                packet_data, (sender_address, sender_port) = self.socket.recvfrom(DEFAULT_BUFFER_SIZE)
                
                if packet_data:
                    try:
                        # Parse packet
                        packet = RTPPacket.from_bytes(packet_data)
                        
                        # Update counters
                        self.packets_received += 1
                        self.bytes_received += len(packet_data)
                        
                        # Call packet handler if set
                        if self.packet_handler:
                            self.packet_handler(packet)
                            
                    except Exception as e:
                        self.logger.error(f"Error parsing RTP packet: {e}")
                        
            except socket.timeout:
                # Socket timeout, just continue the loop
                pass
                
            except Exception as e:
                self.logger.error(f"Error receiving RTP packet: {e}")
                if not self.running:
                    break
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the RTP session.
        
        Returns:
            Dictionary containing session statistics
        """
        return {
            'ssrc': self.ssrc,
            'packets_sent': self.packets_sent,
            'packets_received': self.packets_received,
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
            'send_bitrate': self.bytes_sent * 8 / max(1, self.packets_sent * 0.02) if self.packets_sent > 0 else 0,  # Assuming 20ms packet interval
            'receive_bitrate': self.bytes_received * 8 / max(1, self.packets_received * 0.02) if self.packets_received > 0 else 0
        }
    
    def __del__(self) -> None:
        """Destructor to clean up resources."""
        self.close() 