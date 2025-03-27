"""
Unit tests for RTP packet implementation
"""

import pytest
import struct
from voip_benchmark.rtp import RTPPacket

class TestRTPPacket:
    """Test suite for the RTP packet implementation"""
    
    def test_initialization(self):
        """Test that an RTP packet initializes correctly with default values"""
        payload = b"test payload"
        packet = RTPPacket(payload=payload)
        
        assert packet.payload_type == 0  # Default payload type
        assert packet.sequence_number >= 0
        assert packet.timestamp >= 0
        assert packet.ssrc >= 0
        assert packet.marker == 0
        assert packet.payload == payload
        
    def test_custom_initialization(self):
        """Test initializing an RTP packet with custom values"""
        payload = b"test payload"
        packet = RTPPacket(
            payload_type=96,
            payload=payload,
            sequence_number=1000,
            timestamp=50000,
            ssrc=0xabcdef,
            marker=1
        )
        
        assert packet.payload_type == 96
        assert packet.sequence_number == 1000
        assert packet.timestamp == 50000
        assert packet.ssrc == 0xabcdef
        assert packet.marker == 1
        assert packet.payload == payload
        
    def test_to_bytes_from_bytes(self):
        """Test converting a packet to bytes and back"""
        original = RTPPacket(
            payload_type=96,
            payload=b"test payload",
            sequence_number=1000,
            timestamp=50000,
            ssrc=0xabcdef,
            marker=1
        )
        
        # Convert to bytes
        packet_bytes = original.to_bytes()
        
        # Recreate from bytes
        recreated = RTPPacket.from_bytes(packet_bytes)
        
        # Check that all fields are preserved
        assert recreated.payload_type == original.payload_type
        assert recreated.sequence_number == original.sequence_number
        assert recreated.timestamp == original.timestamp
        assert recreated.ssrc == original.ssrc
        assert recreated.marker == original.marker
        assert recreated.payload == original.payload
        
    def test_header_length(self):
        """Test that the header length is always 12 bytes"""
        packet = RTPPacket(payload=b"test")
        assert packet.header_length() == 12
        
    def test_packet_length(self):
        """Test packet length calculation"""
        payload = b"test payload"
        packet = RTPPacket(payload=payload)
        
        # Total length should be header (12 bytes) + payload length
        assert packet.packet_length() == 12 + len(payload)
        
    def test_invalid_packet_data(self):
        """Test that invalid packet data raises ValueError"""
        with pytest.raises(ValueError):
            # Too short to be a valid RTP packet
            RTPPacket.from_bytes(b"invalid")
            
    def test_str_representation(self):
        """Test string representation of packet"""
        packet = RTPPacket(
            payload_type=96,
            payload=b"test payload",
            sequence_number=1000,
            timestamp=50000,
            ssrc=0xabcdef
        )
        
        str_rep = str(packet)
        assert "RTP Packet" in str_rep
        assert "PT=96" in str_rep
        assert "SN=1000" in str_rep 