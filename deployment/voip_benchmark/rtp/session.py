"""
RTP Session Implementation

This module provides an RTP session implementation that manages
sending and receiving RTP packets over UDP.
"""

import socket
import logging
import threading
import time
from typing import Optional, Tuple, List, Dict, Any, Callable

from voip_benchmark.rtp.packet import RTPPacket


class RTPSession:
    """RTP session implementation.
    
    This class manages sending and receiving RTP packets over UDP.
    """
    
    def __init__(self, 
                 local_address: str = '0.0.0.0',
                 local_port: int = 0,
                 remote_address: Optional[str] = None,
                 remote_port: Optional[int] = None):
        """Initialize an RTP session.
        
        Args:
            local_address: Local IP address to bind to
            local_port: Local port to bind to
            remote_address: Remote IP address to send to
            remote_port: Remote port to send to
        """
        self.local_address = local_address
        self.local_port = local_port
        self.remote_address = remote_address
        self.remote_port = remote_port
        
        # Statistics
        self.packets_sent = 0
        self.packets_received = 0
        self.bytes_sent = 0
        self.bytes_received = 0
        self.start_time = None
        
        # Socket
        self.socket = None
        self.running = False
        self.receive_thread = None
        
        # Callbacks
        self.packet_callback = None
        
        # Initialize socket
        self._init_socket()
    
    def _init_socket(self) -> None:
        """Initialize UDP socket."""
        try:
            # Create UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # Set socket options
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to local address and port
            self.socket.bind((self.local_address, self.local_port))
            
            # Get assigned port (if we used port 0)
            self.local_port = self.socket.getsockname()[1]
            
            # Set a reasonable timeout for operations
            self.socket.settimeout(0.1)
            
            logging.debug(f"RTP session initialized on {self.local_address}:{self.local_port}")
            
        except Exception as e:
            logging.error(f"Failed to initialize RTP session: {e}")
            raise
    
    def set_remote_endpoint(self, address: str, port: int) -> None:
        """Set the remote endpoint for sending packets.
        
        Args:
            address: Remote IP address
            port: Remote port
        """
        self.remote_address = address
        self.remote_port = port
        logging.debug(f"Remote endpoint set to {address}:{port}")
    
    def start_receiving(self, callback: Callable[[RTPPacket, Tuple[str, int]], None]) -> None:
        """Start receiving RTP packets.
        
        Args:
            callback: Function to call when a packet is received. 
                     Takes (packet, source_address) as arguments.
        """
        if self.running:
            return
            
        self.packet_callback = callback
        self.running = True
        self.start_time = time.time()
        
        # Start receive thread
        self.receive_thread = threading.Thread(target=self._receive_loop)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        
        logging.debug("RTP receive thread started")
    
    def _receive_loop(self) -> None:
        """Receive loop for RTP packets."""
        while self.running:
            try:
                # Receive packet
                data, addr = self.socket.recvfrom(2048)
                
                # Update statistics
                self.packets_received += 1
                self.bytes_received += len(data)
                
                try:
                    # Parse as RTP packet
                    packet = RTPPacket.from_bytes(data)
                    
                    # Call callback if set
                    if self.packet_callback:
                        self.packet_callback(packet, addr)
                        
                except Exception as e:
                    logging.warning(f"Failed to parse RTP packet: {e}")
                    
            except socket.timeout:
                # Just a timeout, continue
                pass
            except Exception as e:
                if self.running:
                    logging.error(f"Error in RTP receive loop: {e}")
    
    def stop_receiving(self) -> None:
        """Stop receiving RTP packets."""
        self.running = False
        
        if self.receive_thread:
            # Wait for thread to finish
            if self.receive_thread.is_alive():
                self.receive_thread.join(1.0)
            self.receive_thread = None
            
        logging.debug("RTP receive thread stopped")
    
    def send_packet(self, packet: RTPPacket) -> bool:
        """Send an RTP packet.
        
        Args:
            packet: RTP packet to send
            
        Returns:
            True if the packet was sent, False otherwise
        """
        if not self.remote_address or not self.remote_port:
            logging.error("Cannot send packet: No remote endpoint set")
            return False
            
        try:
            # Convert packet to bytes
            packet_data = packet.to_bytes()
            
            # Send packet
            bytes_sent = self.socket.sendto(packet_data, (self.remote_address, self.remote_port))
            
            # Update statistics
            self.packets_sent += 1
            self.bytes_sent += bytes_sent
            
            return True
            
        except Exception as e:
            logging.error(f"Failed to send RTP packet: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get session statistics.
        
        Returns:
            Dictionary of statistics
        """
        elapsed = time.time() - (self.start_time or time.time())
        
        return {
            'packets_sent': self.packets_sent,
            'packets_received': self.packets_received,
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
            'send_rate': self.bytes_sent / elapsed if elapsed > 0 else 0,
            'receive_rate': self.bytes_received / elapsed if elapsed > 0 else 0,
            'elapsed_time': elapsed
        }
    
    def close(self) -> None:
        """Close the RTP session."""
        if self.running:
            self.stop_receiving()
            
        if self.socket:
            try:
                self.socket.close()
            except Exception as e:
                logging.warning(f"Error closing RTP session socket: {e}")
            finally:
                self.socket = None
                
        logging.debug("RTP session closed") 