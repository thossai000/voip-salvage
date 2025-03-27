"""
Network Utilities

This module provides utility functions for network operations.
"""

import time
import socket
import random
import threading
import subprocess
from typing import Optional, Dict, List, Tuple, Any, Union, Callable


def check_port_available(host: str, port: int, timeout: float = 1.0) -> bool:
    """Check if a port is available.
    
    Args:
        host: Host to check
        port: Port to check
        timeout: Timeout in seconds
        
    Returns:
        True if the port is available, False otherwise
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    result = sock.connect_ex((host, port))
    sock.close()
    return result != 0


def get_free_port(start_port: int = 10000, end_port: int = 60000) -> int:
    """Get a free port.
    
    Args:
        start_port: Start of port range to check
        end_port: End of port range to check
        
    Returns:
        Free port number
        
    Raises:
        RuntimeError: If no free port is found
    """
    for _ in range(100):  # Try up to 100 times
        port = random.randint(start_port, end_port)
        if check_port_available('127.0.0.1', port):
            return port
    raise RuntimeError("No free port found")


def ping(host: str, count: int = 4, timeout: float = 2.0) -> Dict[str, Any]:
    """Ping a host.
    
    Args:
        host: Host to ping
        count: Number of ping packets to send
        timeout: Timeout in seconds
        
    Returns:
        Dictionary containing ping statistics
    """
    try:
        # Determine OS-specific ping command
        import platform
        
        if platform.system().lower() == 'windows':
            count_flag = '-n'
            timeout_flag = '-w'
            timeout_ms = int(timeout * 1000)
        else:
            count_flag = '-c'
            timeout_flag = '-W'
            timeout_ms = int(timeout)
        
        # Run ping command
        cmd = ['ping', count_flag, str(count), timeout_flag, str(timeout_ms), host]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        output = stdout.decode('utf-8', errors='ignore')
        
        # Parse output
        if process.returncode != 0:
            return {
                'success': False,
                'error': stderr.decode('utf-8', errors='ignore') or 'Unknown error',
                'min_rtt': None,
                'avg_rtt': None,
                'max_rtt': None,
                'packet_loss': 100.0
            }
        
        # Extract statistics
        stats = {}
        stats['success'] = True
        
        # Try to extract packet loss
        import re
        loss_match = re.search(r'(\d+)% packet loss', output)
        stats['packet_loss'] = float(loss_match.group(1)) if loss_match else 0.0
        
        # Try to extract RTT
        rtt_match = re.search(r'min/avg/max(?:/mdev)?\s*=\s*([\d.]+)/([\d.]+)/([\d.]+)', output)
        if rtt_match:
            stats['min_rtt'] = float(rtt_match.group(1))
            stats['avg_rtt'] = float(rtt_match.group(2))
            stats['max_rtt'] = float(rtt_match.group(3))
        else:
            stats['min_rtt'] = None
            stats['avg_rtt'] = None
            stats['max_rtt'] = None
        
        return stats
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'min_rtt': None,
            'avg_rtt': None,
            'max_rtt': None,
            'packet_loss': 100.0
        }


class NetworkSimulator:
    """Network simulator for packet loss, delay, and jitter.
    
    This class provides a simple network simulator for testing
    network impairments.
    """
    
    def __init__(self,
                packet_loss_rate: float = 0.0,
                delay_ms: float = 0.0,
                jitter_ms: float = 0.0,
                out_of_order_rate: float = 0.0,
                duplicate_rate: float = 0.0):
        """Initialize the network simulator.
        
        Args:
            packet_loss_rate: Packet loss rate (0.0 to 1.0)
            delay_ms: Delay in milliseconds
            jitter_ms: Jitter in milliseconds
            out_of_order_rate: Out-of-order packet rate (0.0 to 1.0)
            duplicate_rate: Duplicate packet rate (0.0 to 1.0)
        """
        self.packet_loss_rate = max(0.0, min(1.0, packet_loss_rate))
        self.delay_ms = max(0.0, delay_ms)
        self.jitter_ms = max(0.0, jitter_ms)
        self.out_of_order_rate = max(0.0, min(1.0, out_of_order_rate))
        self.duplicate_rate = max(0.0, min(1.0, duplicate_rate))
        
        # State
        self.delayed_packets = {}
        self.sequence_number = 0
        self.stop_flag = threading.Event()
        self.simulator_thread = None
    
    def start(self) -> None:
        """Start the network simulator."""
        if self.simulator_thread is not None:
            return
            
        self.stop_flag.clear()
        self.simulator_thread = threading.Thread(target=self._simulator_loop)
        self.simulator_thread.daemon = True
        self.simulator_thread.start()
    
    def stop(self) -> None:
        """Stop the network simulator."""
        self.stop_flag.set()
        if self.simulator_thread:
            self.simulator_thread.join(timeout=2.0)
            self.simulator_thread = None
    
    def send(self, data: bytes, on_receive: Callable[[bytes], None]) -> None:
        """Send data through the network simulator.
        
        Args:
            data: Data to send
            on_receive: Callback function called when data is received
        """
        # Assign sequence number to packet
        sequence_number = self.sequence_number
        self.sequence_number += 1
        
        # Check for packet loss
        if random.random() < self.packet_loss_rate:
            # Packet lost
            return
        
        # Check for duplicate packet
        if random.random() < self.duplicate_rate:
            # Schedule duplicate packet
            self._schedule_packet(data, on_receive, sequence_number)
        
        # Schedule original packet
        self._schedule_packet(data, on_receive, sequence_number)
    
    def _schedule_packet(self, data: bytes, on_receive: Callable[[bytes], None], sequence_number: int) -> None:
        """Schedule a packet for delivery.
        
        Args:
            data: Packet data
            on_receive: Callback function called when packet is received
            sequence_number: Packet sequence number
        """
        # Calculate delay
        delay_ms = self.delay_ms
        
        # Add jitter
        if self.jitter_ms > 0:
            # Uniform jitter between -jitter_ms and +jitter_ms
            jitter = random.uniform(-self.jitter_ms, self.jitter_ms)
            delay_ms += jitter
        
        # Check for out-of-order packet
        if random.random() < self.out_of_order_rate:
            # Add extra delay to simulate out-of-order packet
            delay_ms += random.uniform(0, self.delay_ms * 2)
        
        # Ensure delay is not negative
        delay_ms = max(0.0, delay_ms)
        
        # Calculate delivery time
        delivery_time = time.time() + (delay_ms / 1000.0)
        
        # Add to delayed packets
        self.delayed_packets[sequence_number] = (delivery_time, data, on_receive)
    
    def _simulator_loop(self) -> None:
        """Main simulator loop."""
        while not self.stop_flag.is_set():
            current_time = time.time()
            
            # Find packets to deliver
            delivered_packets = []
            for sequence_number, (delivery_time, data, on_receive) in self.delayed_packets.items():
                if current_time >= delivery_time:
                    # Deliver packet
                    try:
                        on_receive(data)
                    except Exception:
                        pass
                    delivered_packets.append(sequence_number)
            
            # Remove delivered packets
            for sequence_number in delivered_packets:
                del self.delayed_packets[sequence_number]
            
            # Sleep for a short time
            time.sleep(0.001)


def get_network_interfaces() -> Dict[str, Dict[str, Any]]:
    """Get information about network interfaces.
    
    Returns:
        Dictionary mapping interface names to interface information
    """
    interfaces = {}
    
    try:
        import netifaces
        
        for iface in netifaces.interfaces():
            ifaddrs = netifaces.ifaddresses(iface)
            
            # Skip interfaces without IPv4 addresses
            if netifaces.AF_INET not in ifaddrs:
                continue
            
            # Get IPv4 address information
            ipv4_info = ifaddrs[netifaces.AF_INET][0]
            
            # Get MAC address if available
            mac_address = None
            if netifaces.AF_LINK in ifaddrs:
                mac_info = ifaddrs[netifaces.AF_LINK][0]
                mac_address = mac_info.get('addr')
            
            # Add interface information
            interfaces[iface] = {
                'ip_address': ipv4_info.get('addr'),
                'netmask': ipv4_info.get('netmask'),
                'broadcast': ipv4_info.get('broadcast'),
                'mac_address': mac_address
            }
    except ImportError:
        # Fallback to socket-based approach
        import socket
        
        # Get hostname and IP address
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        
        interfaces['default'] = {
            'ip_address': ip_address,
            'netmask': None,
            'broadcast': None,
            'mac_address': None
        }
    
    return interfaces


def get_free_udp_port_pair(base_port: int = 10000, max_attempts: int = 100) -> Tuple[int, int]:
    """Get a pair of free UDP ports.
    
    Args:
        base_port: Base port number
        max_attempts: Maximum number of attempts
        
    Returns:
        Tuple of (port1, port2)
        
    Raises:
        RuntimeError: If no free port pair is found
    """
    for _ in range(max_attempts):
        port1 = random.randint(base_port, 60000)
        port2 = port1 + 2  # Use even-numbered ports for RTP, odd for RTCP
        
        # Check if both ports are available
        if check_port_available('127.0.0.1', port1, timeout=0.1) and \
           check_port_available('127.0.0.1', port2, timeout=0.1):
            return port1, port2
    
    raise RuntimeError("No free UDP port pair found")


def resolve_hostname(hostname: str) -> Optional[str]:
    """Resolve a hostname to an IP address.
    
    Args:
        hostname: Hostname to resolve
        
    Returns:
        IP address or None if resolution fails
    """
    try:
        return socket.gethostbyname(hostname)
    except socket.error:
        return None


def is_valid_ip_address(ip_address: str) -> bool:
    """Check if an IP address is valid.
    
    Args:
        ip_address: IP address to check
        
    Returns:
        True if the IP address is valid, False otherwise
    """
    try:
        socket.inet_aton(ip_address)
        return True
    except socket.error:
        return False


def check_udp_connectivity(host: str, port: int, timeout: float = 2.0) -> bool:
    """Check UDP connectivity to a host and port.
    
    Args:
        host: Host to check
        port: Port to check
        timeout: Timeout in seconds
        
    Returns:
        True if connectivity is available, False otherwise
    """
    try:
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        
        # Send a packet
        sock.sendto(b'ping', (host, port))
        
        # Try to receive a response
        try:
            sock.recvfrom(1024)
            return True
        except socket.timeout:
            return False
    except socket.error:
        return False
    finally:
        sock.close() 