"""
VoIP Benchmarking Framework

This package provides tools for benchmarking VoIP audio quality
under various network conditions.
"""

__version__ = '1.0.0'

# Import main components for easier access
from voip_benchmark.codecs import get_codec
from voip_benchmark.rtp import RTPPacket, RTPSession, RTPStream
from voip_benchmark.codecs.adaptive_bitrate import AdaptiveBitrateController 