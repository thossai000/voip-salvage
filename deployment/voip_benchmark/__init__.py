"""
VoIP Benchmarking Framework

This package provides tools for benchmarking VoIP audio quality
under various network conditions.
"""

__version__ = '1.0.0'

# Import main components for easier access
from voip_benchmark.codecs import get_codec, CodecBase, OpusCodec
from voip_benchmark.rtp import RTPPacket, RTPSession, RTPStream, NetworkSimulator, NetworkConditions
from voip_benchmark.codecs.adaptive_bitrate import AdaptiveBitrateController, AdaptiveBitrateStrategy
from voip_benchmark.utils.audio import read_wav_file, write_wav_file, generate_sine_wave, audio_signal_statistics
from voip_benchmark.utils.config import get_default_config, load_config
from voip_benchmark.utils.statistics import calculate_mos, calculate_compression_ratio 