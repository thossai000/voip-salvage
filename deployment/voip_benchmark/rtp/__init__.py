"""
RTP Implementation for VoIP Benchmarking

This package provides RTP (Real-time Transport Protocol) implementation
for VoIP benchmarking.
"""

# Import main RTP components for easier access
from voip_benchmark.rtp.packet import RTPPacket, PAYLOAD_TYPE_OPUS, PAYLOAD_TYPE_PCMU, PAYLOAD_TYPE_PCMA
from voip_benchmark.rtp.session import RTPSession
from voip_benchmark.rtp.stream import RTPStream
from voip_benchmark.rtp.simulator import NetworkSimulator, NetworkConditions 