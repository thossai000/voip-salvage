"""
Utility Modules for VoIP Benchmarking

This package provides utility functions and classes
for the VoIP benchmarking framework.
"""

# Import utility functions for easier access
from voip_benchmark.utils.audio import (
    read_wav_file, 
    write_wav_file, 
    generate_sine_wave,
    convert_wav_format,
    audio_signal_statistics,
    get_wav_file_info,
    concat_wav_files
)

from voip_benchmark.utils.config import (
    get_default_config,
    load_config,
    save_config,
    update_config,
    validate_config,
    get_config_value
)

from voip_benchmark.utils.statistics import (
    calculate_mos,
    calculate_packet_loss_ratio,
    calculate_packet_loss_burst_ratio,
    calculate_jitter_statistics,
    calculate_psnr,
    calculate_compression_ratio,
    calculate_audio_level,
    generate_voip_report
) 