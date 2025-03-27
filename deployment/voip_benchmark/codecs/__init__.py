"""
VoIP Benchmark Codec Implementations

This package contains implementations of various audio codecs
for VoIP benchmarking purposes.
"""

from voip_benchmark.codecs.base import CodecBase
from voip_benchmark.codecs.opus import OpusCodec

# Dictionary of available codecs
AVAILABLE_CODECS = {
    'opus': OpusCodec,
}

def get_codec(codec_name):
    """Get a codec class by name.
    
    Args:
        codec_name (str): Name of the codec to get
        
    Returns:
        CodecBase: The codec class
        
    Raises:
        ValueError: If the codec is not available
    """
    if codec_name not in AVAILABLE_CODECS:
        raise ValueError(f"Codec '{codec_name}' not available")
    return AVAILABLE_CODECS[codec_name] 