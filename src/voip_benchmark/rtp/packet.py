#!/usr/bin/env python3

import struct
import time
import random
import logging

class RTPPacket:
    """
    Implements basic RTP packet functionality.
    Based on RFC 3550.
    """
    
    # RTP header field offsets
    VERSION_OFFSET = 0
    PADDING_OFFSET = 1
    EXTENSION_OFFSET = 2
    CSRC_COUNT_OFFSET = 3
    MARKER_OFFSET = 7
    PAYLOAD_TYPE_OFFSET = 0
    SEQ_NUM_OFFSET = 2
    TIMESTAMP_OFFSET = 4
    SSRC_OFFSET = 8
    
    # Header size constants
    HEADER_SIZE = 12  # Minimum RTP header size without CSRCs or extensions
    
    def __init__(self, version=2, padding=0, extension=0, csrc_count=0, 
                 marker=0, payload_type=0, sequence_number=0, timestamp=0,
                 ssrc=0, payload=b''):
        """
        Initialize RTP packet with given parameters.
        
        Args:
            version: RTP version (default: 2)
            padding: Padding flag (default: 0)
            extension: Extension flag (default: 0)
            csrc_count: CSRC count (default: 0)
            marker: Marker bit (default: 0)
            payload_type: Payload type identifier (default: 0)
            sequence_number: Packet sequence number (default: 0)
            timestamp: Packet timestamp (default: 0)
            ssrc: Synchronization source identifier (default: 0)
            payload: Packet payload data (default: empty bytes)
        """
        self.version = version
        self.padding = padding
        self.extension = extension
        self.csrc_count = csrc_count
        self.marker = marker
        self.payload_type = payload_type
        self.sequence_number = sequence_number
        self.timestamp = timestamp
        self.ssrc = ssrc
        self.csrc_list = []
        self.extension_data = b''
        self.payload = payload
        
    def get_header(self):
        """
        Build the RTP header.
        
        Returns:
            bytes: RTP header as bytes
        """
        # First byte: version (2 bits), padding (1 bit), extension (1 bit), CSRC count (4 bits)
        first_byte = ((self.version & 0x03) << 6) | \
                     ((self.padding & 0x01) << 5) | \
                     ((self.extension & 0x01) << 4) | \
                     (self.csrc_count & 0x0F)
        
        # Second byte: marker (1 bit), payload type (7 bits)
        second_byte = ((self.marker & 0x01) << 7) | \
                      (self.payload_type & 0x7F)
        
        # Rest of the header
        header = struct.pack(
            '!BBHLLs',
            first_byte,
            second_byte,
            self.sequence_number,
            self.timestamp,
            self.ssrc,
            bytes()  # Placeholder for CSRC list and extension
        )
        
        return header[:-1]  # Strip empty placeholder
        
    def get_packet(self):
        """
        Build the complete RTP packet.
        
        Returns:
            bytes: Complete RTP packet including header and payload
        """
        header = self.get_header()
        
        # Add CSRC list if any
        csrc_data = b''
        for csrc in self.csrc_list:
            csrc_data += struct.pack('!L', csrc)
        
        # Add extension if any
        extension_data = b''
        if self.extension:
            extension_data = self.extension_data
        
        # Combine all parts
        packet = header + csrc_data + extension_data + self.payload
        
        return packet
        
    def parse_packet(self, packet_data):
        """
        Parse RTP packet from bytes.
        
        Args:
            packet_data: Raw packet data as bytes
            
        Returns:
            bool: True if parsing succeeded, False otherwise
        """
        try:
            if len(packet_data) < self.HEADER_SIZE:
                logging.error("Packet too small to be a valid RTP packet")
                return False
            
            # Parse header fields
            first_byte = packet_data[0]
            self.version = (first_byte >> 6) & 0x03
            self.padding = (first_byte >> 5) & 0x01
            self.extension = (first_byte >> 4) & 0x01
            self.csrc_count = first_byte & 0x0F
            
            second_byte = packet_data[1]
            self.marker = (second_byte >> 7) & 0x01
            self.payload_type = second_byte & 0x7F
            
            self.sequence_number = struct.unpack('!H', packet_data[2:4])[0]
            self.timestamp = struct.unpack('!L', packet_data[4:8])[0]
            self.ssrc = struct.unpack('!L', packet_data[8:12])[0]
            
            # Parse CSRC list if any
            offset = 12  # Start after header
            self.csrc_list = []
            for i in range(self.csrc_count):
                if offset + 4 <= len(packet_data):
                    csrc = struct.unpack('!L', packet_data[offset:offset+4])[0]
                    self.csrc_list.append(csrc)
                    offset += 4
                else:
                    logging.error("Packet too small for CSRC list")
                    return False
            
            # Parse extension if any
            if self.extension:
                if offset + 4 <= len(packet_data):
                    ext_header = struct.unpack('!HH', packet_data[offset:offset+4])
                    ext_profile = ext_header[0]
                    ext_length = ext_header[1] * 4  # Length in 32-bit words
                    
                    offset += 4
                    if offset + ext_length <= len(packet_data):
                        self.extension_data = packet_data[offset:offset+ext_length]
                        offset += ext_length
                    else:
                        logging.error("Packet too small for extension data")
                        return False
                else:
                    logging.error("Packet too small for extension header")
                    return False
            
            # Extract payload
            self.payload = packet_data[offset:]
            
            return True
            
        except Exception as e:
            logging.error(f"Error parsing RTP packet: {e}")
            return False
    
    def __str__(self):
        """String representation of the RTP packet"""
        return (f"RTP Packet [V={self.version}, P={self.padding}, X={self.extension}, "
                f"CC={self.csrc_count}, M={self.marker}, PT={self.payload_type}, "
                f"SN={self.sequence_number}, TS={self.timestamp}, SSRC={self.ssrc}, "
                f"Payload size={len(self.payload)} bytes]")


def create_rtp_packet(payload, seq_num, timestamp, ssrc=None, payload_type=96):
    """
    Utility function to create an RTP packet.
    
    Args:
        payload: Packet payload
        seq_num: Sequence number
        timestamp: Timestamp
        ssrc: Synchronization source identifier (random if None)
        payload_type: Payload type (default: 96 = dynamic)
        
    Returns:
        RTPPacket: Created RTP packet
    """
    if ssrc is None:
        ssrc = random.randint(0, 0xFFFFFFFF)
        
    packet = RTPPacket(
        version=2,
        padding=0,
        extension=0,
        csrc_count=0,
        marker=0,
        payload_type=payload_type,
        sequence_number=seq_num,
        timestamp=timestamp,
        ssrc=ssrc,
        payload=payload
    )
    
    return packet


if __name__ == "__main__":
    # Create a test packet
    test_payload = b"Test RTP payload data"
    packet = create_rtp_packet(
        payload=test_payload,
        seq_num=1234,
        timestamp=int(time.time() * 1000),
        payload_type=96
    )
    
    # Get binary packet data
    packet_data = packet.get_packet()
    print(f"Created packet: {packet}")
    print(f"Packet size: {len(packet_data)} bytes")
    
    # Parse the packet data back into a new packet
    new_packet = RTPPacket()
    if new_packet.parse_packet(packet_data):
        print(f"Parsed packet: {new_packet}")
        print(f"Payload: {new_packet.payload}")
    else:
        print("Failed to parse packet") 