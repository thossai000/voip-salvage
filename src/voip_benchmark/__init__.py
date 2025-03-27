"""
VoIP Benchmark Package

A benchmarking framework for VoIP codec performance testing.
"""

__version__ = '0.1.0'
__author__ = 'VoIP Benchmark Team'

# Import main components for easier access
from voip_benchmark.codecs.base import CodecBase
from voip_benchmark.codecs.opus import OpusCodec

# Define package-level constants
DEFAULT_SAMPLE_RATE = 48000
DEFAULT_CHANNELS = 1
DEFAULT_FRAME_SIZE = 960  # 20ms at 48kHz 