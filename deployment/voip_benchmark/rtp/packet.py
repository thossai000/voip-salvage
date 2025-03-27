"""
RTP Packet Implementation

This module provides functionality for creating, parsing, and manipulating
RTP (Real-time Transport Protocol) packets.
"""

import time
import random
import struct
from typing import Optional, Tuple, List, Dict, Any

# RTP header constants
RTP_VERSION = 2  # RTP version 2
RTP_PADDING = 0  # No padding by default
RTP_EXTENSION = 0  # No extension by default
RTP_CSRC_COUNT = 0  # No contributing sources by default
RTP_MARKER = 0  # Marker bit (0 by default)

# Common payload types (RFC 3551)
PAYLOAD_TYPE_PCMU = 0  # G.711 mu-law
PAYLOAD_TYPE_GSM = 3   # GSM
PAYLOAD_TYPE_G723 = 4  # G.723
PAYLOAD_TYPE_PCMA = 8  # G.711 A-law
PAYLOAD_TYPE_G722 = 9  # G.722
PAYLOAD_TYPE_OPUS = 111  # Opus (dynamic payload type)

# Maximum packet size
MAX_PACKET_SIZE = 1500  # Typical Ethernet MTU


class RTPPacket:
    """RTP packet implementation.
    
    This class provides functionality for creating, parsing, and manipulating
    RTP packets.
    """
    
    def __init__(self, 
                 payload_type: int = PAYLOAD_TYPE_OPUS,
                 payload: bytes = b'',
                 sequence_number: Optional[int] = None,
                 timestamp: Optional[int] = None,
                 ssrc: Optional[int] = None,
                 marker: bool = False):
        """Initialize an RTP packet.
        
        Args:
            payload_type: RTP payload type
            payload: Packet payload data
            sequence_number: Packet sequence number (auto-generated if None)
            timestamp: Packet timestamp (auto-generated if None)
            ssrc: Synchronization source identifier (auto-generated if None)
            marker: Marker bit (usually set for the first packet in a talk spurt)
        """
        self.version = RTP_VERSION
        self.padding = RTP_PADDING
        self.extension = RTP_EXTENSION
        self.csrc_count = RTP_CSRC_COUNT
        self.marker = 1 if marker else 0
        self.payload_type = payload_type
        
        # Generate sequence number if not provided
        if sequence_number is None:
            self.sequence_number = random.randint(0, 0xFFFF)
        else:
            self.sequence_number = sequence_number & 0xFFFF  # 16 bits
        
        # Generate timestamp if not provided
        if timestamp is None:
            self.timestamp = int(time.time() * 1000)  # Use current time in milliseconds
        else:
            self.timestamp = timestamp
        
        # Generate SSRC if not provided
        if ssrc is None:
            self.ssrc = random.randint(0, 0xFFFFFFFF)
        else:
            self.ssrc = ssrc & 0xFFFFFFFF  # 32 bits
        
        # CSRC list (empty by default)
        self.csrc_list = []
        
        # Payload data
        self.payload = payload
    
    @classmethod
    def from_bytes(cls, packet_data: bytes) -> 'RTPPacket':
        """Parse an RTP packet from bytes.
        
        Args:
            packet_data: Raw packet data
            
        Returns:
            RTPPacket object
            
        Raises:
            ValueError: If the packet data is invalid
        """
        if len(packet_data) < 12:  # Minimum RTP header size
            raise ValueError("Packet data too short for RTP header")
        
        # Parse header
        header = struct.unpack('!BBHII', packet_data[:12])
        
        # Extract header fields
        version = (header[0] >> 6) & 0x3
        padding = (header[0] >> 5) & 0x1
        extension = (header[0] >> 4) & 0x1
        csrc_count = header[0] & 0xF
        marker = (header[1] >> 7) & 0x1
        payload_type = header[1] & 0x7F
        sequence_number = header[2]
        timestamp = header[3]
        ssrc = header[4]
        
        # Validate version
        if version != RTP_VERSION:
            raise ValueError(f"Unsupported RTP version: {version}")
        
        # Create packet
        packet = cls(
            payload_type=payload_type,
            sequence_number=sequence_number,
            timestamp=timestamp,
            ssrc=ssrc,
            marker=(marker == 1)
        )
        
        packet.padding = padding
        packet.extension = extension
        packet.csrc_count = csrc_count
        
        # Parse CSRC list
        offset = 12
        packet.csrc_list = []
        for i in range(csrc_count):
            if offset + 4 > len(packet_data):
                raise ValueError("Packet data too short for CSRC list")
            csrc = struct.unpack('!I', packet_data[offset:offset+4])[0]
            packet.csrc_list.append(csrc)
            offset += 4
        
        # Parse extension if present
        if extension:
            if offset + 4 > len(packet_data):
                raise ValueError("Packet data too short for extension header")
            ext_header = struct.unpack('!HH', packet_data[offset:offset+4])
            profile = ext_header[0]
            length = ext_header[1] * 4  # Length in bytes
            offset += 4
            
            if offset + length > len(packet_data):
                raise ValueError("Packet data too short for extension data")
            
            # Skip extension data
            offset += length
        
        # Extract payload (removing padding if present)
        if padding:
            if offset >= len(packet_data):
                raise ValueError("No padding byte found")
                
            # Last byte contains padding length
            padding_length = packet_data[-1]
            
            if padding_length <= 0 or offset + padding_length > len(packet_data):
                raise ValueError(f"Invalid padding length: {padding_length}")
                
            packet.payload = packet_data[offset:-padding_length]
        else:
            packet.payload = packet_data[offset:]
        
        return packet
    
    def to_bytes(self) -> bytes:
        """Convert the RTP packet to bytes.
        
        Returns:
            Raw packet data
        """
        # Validate CSRC count
        if len(self.csrc_list) != self.csrc_count:
            self.csrc_count = len(self.csrc_list)
        
        # Calculate header first byte:
        # 2 bits for version, 1 bit for padding, 1 bit for extension, 4 bits for CSRC count
        first_byte = ((self.version & 0x3) << 6) | \
                     ((self.padding & 0x1) << 5) | \
                     ((self.extension & 0x1) << 4) | \
                     (self.csrc_count & 0xF)
        
        # Calculate header second byte:
        # 1 bit for marker, 7 bits for payload type
        second_byte = ((self.marker & 0x1) << 7) | \
                      (self.payload_type & 0x7F)
        
        # Create header
        header = struct.pack('!BBHII',
                            first_byte,
                            second_byte,
                            self.sequence_number & 0xFFFF,  # 16 bits
                            self.timestamp & 0xFFFFFFFF,    # 32 bits
                            self.ssrc & 0xFFFFFFFF)         # 32 bits
        
        # Add CSRC list
        csrc_data = b''
        for csrc in self.csrc_list[:16]:  # Maximum 16 CSRCs
            csrc_data += struct.pack('!I', csrc & 0xFFFFFFFF)  # 32 bits
        
        # Return complete packet
        return header + csrc_data + self.payload
    
    def get_header_length(self) -> int:
        """Get the length of the RTP header.
        
        Returns:
            Header length in bytes
        """
        # 12 bytes for the fixed header plus 4 bytes per CSRC
        return 12 + (self.csrc_count * 4)
    
    def get_payload_length(self) -> int:
        """Get the length of the payload.
        
        Returns:
            Payload length in bytes
        """
        return len(self.payload)
    
    def get_packet_length(self) -> int:
        """Get the total length of the packet.
        
        Returns:
            Packet length in bytes
        """
        return self.get_header_length() + self.get_payload_length()
    
    def __str__(self) -> str:
        """Get a string representation of the packet.
        
        Returns:
            String representation
        """
        return f"RTPPacket(PT={self.payload_type}, SN={self.sequence_number}, TS={self.timestamp}, SSRC={self.ssrc:08x}, payload={len(self.payload)} bytes)"
    
    def __repr__(self) -> str:
        """Get a detailed string representation of the packet.
        
        Returns:
            String representation
        """
        return f"RTPPacket(version={self.version}, padding={self.padding}, extension={self.extension}, " \
               f"csrc_count={self.csrc_count}, marker={self.marker}, payload_type={self.payload_type}, " \
               f"sequence_number={self.sequence_number}, timestamp={self.timestamp}, ssrc=0x{self.ssrc:08x}, " \
               f"payload_length={len(self.payload)})" 